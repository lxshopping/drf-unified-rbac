# V3 实现与验收报告

分支：codex/v3-adapter-rbac。版本：0.3.0。日期：2026-09-18。
未执行 git commit；工作区修改供人工 review。

## 1. V2 原架构

认证由宿主 DRF authenticator 或 KeycloakAuthentication 建立 request.user。
Principal.from_user 区分 Local Django user 与 SSOUser。LocalRoleProvider 根据
UserRole 查询启用角色；SSORoleProvider 将已验证 token 的 client roles 与启用
RBAC Role 相交；HybridRoleProvider 按 auth_source 选择一个来源。随后
AuthorizationService / PermissionRepository 查询 RolePermission 和启用 Permission。
RBACPermission 支持 APIView 与 ViewSet 声明；me 返回统一身份与授权信息。
Admin API 使用同一 RBACPermission。UserRole 和初始 migration 已兼容 AUTH_USER_MODEL。
V2 基线测试为 156 passed；当前实现无需重写这些核心模块。

## 2. V3 最终架构

增加独立的登录凭证 Adapter；其调用范围限定为内置登录或宿主主动复用。
授权服务继续仅接收 Principal，不读取 Session、Bearer 或密码。
不新增 User model、密码表、JWT、第三方依赖或数据库迁移。
Keycloak 验签实现、Role/Permission 模型、providers、AuthorizationService、
RBACPermission、Admin API 均保留原实现。

## 3–4. 修改文件和原因

| 文件 | 原因 |
| --- | --- |
| [MANIFEST.in](MANIFEST.in) | 将迁移指南纳入 sdist；沿用现有 Python package discovery。 |
| [README.md](README.md) | 说明四种接入场景、Local/CSRF contract、自定义 Adapter、Hybrid 顺序及可运行示例。 |
| [docs/migration-v2-v3.md](docs/migration-v2-v3.md) | 记录 V2 升级兼容性与 Bearer 优先级变化。 |
| [example_project/config/settings.py](example_project/config/settings.py) | 展示 Local 设置；Hybrid 改为 Keycloak 优先。 |
| [pyproject.toml](pyproject.toml) | 版本从 0.2.0 更新到 0.3.0，依赖范围未改。 |
| [src/drf_unified_rbac/__init__.py](src/drf_unified_rbac/__init__.py) | 同步运行时版本 0.3.0。 |
| [src/drf_unified_rbac/authentication/__init__.py](src/drf_unified_rbac/authentication/__init__.py) | 延迟加载 Keycloak，纯 Local 安装不导入 joserfc，保留原导出。 |
| [src/drf_unified_rbac/authentication/adapters/__init__.py](src/drf_unified_rbac/authentication/adapters/__init__.py) | 公开 BaseLocalAuthAdapter 和 DjangoLocalAuthAdapter。 |
| [src/drf_unified_rbac/authentication/adapters/base.py](src/drf_unified_rbac/authentication/adapters/base.py) | 定义凭证验证接口、失败行为与 Django Session backend 要求。 |
| [src/drf_unified_rbac/authentication/adapters/django.py](src/drf_unified_rbac/authentication/adapters/django.py) | 默认委托 django.contrib.auth.authenticate。 |
| [src/drf_unified_rbac/authentication/views.py](src/drf_unified_rbac/authentication/views.py) | 实现 CSRF 初始化、登录及退出；异常身份拒绝，隐藏凭证异常详情。 |
| [src/drf_unified_rbac/conf.py](src/drf_unified_rbac/conf.py) | 沿用 DRF_RBAC，增加两个默认配置并校验模式、布尔值及 Adapter 路径。 |
| [src/drf_unified_rbac/domain/principal.py](src/drf_unified_rbac/domain/principal.py) | 保留 from_user；新增显式 from_sso(SSOUser) 边界入口。 |
| [src/drf_unified_rbac/factories/__init__.py](src/drf_unified_rbac/factories/__init__.py) | 公开 get_local_auth_adapter。 |
| [src/drf_unified_rbac/factories/authentication.py](src/drf_unified_rbac/factories/authentication.py) | 延迟 dotted-path 加载、子类和构造校验，错误抛 ImproperlyConfigured。 |
| [src/drf_unified_rbac/urls.py](src/drf_unified_rbac/urls.py) | 挂载三个 Local 端点，原 me 和 admin 路径保留。 |
| [src/drf_unified_rbac/views.py](src/drf_unified_rbac/views.py) | me 在 sso/hybrid 中优先验证 Keycloak Bearer，继续消费宿主身份。 |
| [tests/custom_user_check.py](tests/custom_user_check.py) | 扩展既有 UUID/custom USERNAME_FIELD 测试，验证真实登录、Session 恢复和退出。 |
| [tests/test_local_authentication.py](tests/test_local_authentication.py) | 新增 36 个测试实例覆盖 V3 Local、Host、Hybrid、Adapter、CSRF 与错误配置。 |
| [V3_IMPLEMENTATION_REPORT.md](V3_IMPLEMENTATION_REPORT.md) | 本次实现和验证报告。 |

## 5. Local Adapter 调用链

get_local_auth_adapter -> dotted path -> BaseLocalAuthAdapter 子类 ->
authenticate(request, username=..., password=...) -> Django-compatible local user。
默认实现调用 Django authenticate，支持 AUTHENTICATION_BACKENDS；工厂每次创建
新实例，避免共享请求或凭证状态。导入或构造错误抛 ImproperlyConfigured。

## 6. 新项目 Local

CSRF bootstrap -> POST login -> Adapter -> Django authenticate -> Django login ->
Session -> DRF SessionAuthentication -> request.user -> Principal.from_user ->
LocalRoleProvider -> UserRole/Role -> AuthorizationService -> RBAC grants。
POST logout 调用 Django logout、清除 Session，返回 204。
登录仅返回 authenticated=true，不复制授权计算。

## 7. Existing Host Local

Host Login -> host DRF authentication -> request.user -> Principal.from_user ->
LocalRoleProvider -> AuthorizationService -> me/RBACPermission。
不调用 package login 或 Adapter；关闭 Local 端点仍然正常授权。
测试使用真实宿主 authenticator，同时配置不可导入的 Adapter 证明二者独立。

## 8. SSO

Bearer -> KeycloakAuthentication（RS256/JWKS、iss/aud/exp/sub）-> SSOUser ->
Principal.from_user 或显式 from_sso -> SSORoleProvider -> RBAC Role/Permission。
不建立本地 SSO 用户；原 Keycloak 测试全部保留。

## 9. Hybrid

有 Bearer：先 Keycloak 验证，失败终止；有效 Bearer 使用 SSO grants。
无 Bearer：Keycloak 返回 None，继续 host/Session authentication，使用 Local grants。
角色来源只由 auth_source 决定，不按 username 匹配，不合并两套身份。
me 强制此顺序；业务/Admin API 仍由宿主配置 authenticator 顺序，示例已修正。
如果宿主自己也使用 Bearer，必须在宿主视图定义明确路由；package me 在
sso/hybrid 将 Bearer 保留给 Keycloak，不自动猜测两个 token 的归属。

## 10. me contract

GET /api/rbac/me 保持原路径、URL name 和四个字段：

```json
{"username":"alice","auth_source":"local","roles":["local"],"permissions":["demo.local.view"]}
```

SSO 同结构；roles/permissions 去重排序并过滤禁用对象。无 grants 返回空数组。
原有单模式来源不匹配时返回空 grants 的语义保留；无效 Principal 拒绝。

## 11. Settings 和端点

在既有 DRF_RBAC 字典中：

- AUTH_MODE：local 默认，支持 sso/hybrid，其他值 ImproperlyConfigured。
- LOCAL_AUTH_ADAPTER：默认 drf_unified_rbac.authentication.adapters.DjangoLocalAuthAdapter。
- LOCAL_LOGIN_ENABLED：默认 True，严格 bool。
- KEYCLOAK_ISSUER/CLIENT_ID/AUDIENCE：沿用原配置和校验。

新增路径无尾斜杠：GET auth/local/csrf、POST auth/local/login、POST auth/local/logout。
登录成功 200 {authenticated:true}，无效凭证统一 401，退出 204。
两种 POST 都对匿名和已认证调用强制 CSRF，CSRF 错误为 403。登录旋转 CSRF
secret，退出前获取新 token。关闭开关或 sso 模式下，三个 Local 端点均为 404。
关闭内置端点不关闭宿主 Local 授权。异常 Adapter 不返回异常原文，也不记录密码/token。

## 12. V2 → V3 兼容性

required_permissions、APIView、RBACPermission、Role/Permission 数据、Keycloak
配置和验证、Admin API/ADMIN_PERMISSIONS、me 字段保留。已有宿主认证无需替换。
有意的安全变化：me 在 sso/hybrid 下 Bearer 优先于 Session；业务/Admin 应采用
相同配置，避免有效 Session 掩盖无效 Bearer。升级指南已明确说明。

## 13. Migration

无新增 migration。现有 UserRole 外键和 swappable_dependency 已使用 AUTH_USER_MODEL。
全项目未发现直接依赖 django.contrib.auth.models.User 的代码；测试里的 AnonymousUser
是合法匿名身份工具。生产未添加用户模型；复用原有测试专用 custom user。

## 14. pytest

开发环境 Python 3.12.14 / Django 5.2.17 / DRF 3.18.1：
最终 python -m pytest -q：192 passed in 6.39s（156 V2 + 36 V3）。
包含真实 Session、宿主认证、禁用端点、错误/失效 Adapter、CSRF cookie/session
两种存储、登录后的 CSRF 旋转、有效 Session 下无效 Bearer拒绝、SSO 身份优先和
不合并 grants。既有 Admin、Keycloak 和自定义用户测试通过。

## 15. Build 与 Django 检查

python -m build 成功（独立 build environment，先 sdist 再从 sdist 构建 wheel）。
python example_project/manage.py check：0 issues。
python example_project/manage.py makemigrations --check --dry-run：No changes detected。
wheel 43 个 Python 模块与工作区源码逐字节相同，包含新增 adapters、认证视图、工厂、
原 migrations/Admin API；不包含测试和 example。sdist 包含测试、example、迁移指南。
git diff --check 通过；无 executable bit/file mode 修改。

## 16. Wheel 安装 smoke

独立 .venv-rbac-030-wheel，不使用 system-site-packages，不安装 editable 项目。
Django 5.2.6 / DRF 3.16.1。先仅安装 base wheel，确认 joserfc 不存在。
python -I import 从该 venv/site-packages 导入 0.3.0。
从 example 的独立副本使用全新内存数据库完成 check/migrate/seed；启用真实 CSRF
完成 login/me/APIView/ViewSet/logout 流程，全数成功。
随后安装同一 wheel 的 sso/dev extras，在无 src 的独立 tests/example 副本运行
全套 pytest：192 passed in 6.67s。pip check：No broken requirements found。

- drf_unified_rbac-0.3.0-py3-none-any.whl：35135 bytes；SHA256 7a3218e51dcebef5512623b15d4c0f22ee35a85ad402ab977970f58d340ce21c。

- drf_unified_rbac-0.3.0.tar.gz：53126 bytes；SHA256 34f80a8c72a61f207b7f8e4d44c10fbbe75eb8b80207521f7c7faa88633ce12e。

## 17. 当前 git diff --stat

```text
 MANIFEST.in                                     |  10 +-
 README.md                                       | 165 ++++++++++++++++++++----
 example_project/config/settings.py              |   4 +-
 pyproject.toml                                  |   2 +-
 src/drf_unified_rbac/__init__.py                |   2 +-
 src/drf_unified_rbac/authentication/__init__.py |  10 +-
 src/drf_unified_rbac/conf.py                    |  13 +-
 src/drf_unified_rbac/domain/principal.py        |   7 +
 src/drf_unified_rbac/factories/__init__.py      |   4 +-
 src/drf_unified_rbac/urls.py                    |   4 +
 src/drf_unified_rbac/views.py                   |  11 ++
 tests/custom_user_check.py                      |  18 ++-
 12 files changed, 213 insertions(+), 37 deletions(-)
```

此命令只统计已跟踪文件；新增 Adapter、认证视图、工厂、测试、迁移指南和本报告尚未 staged，需一并 review。

验证范围：SQLite 与本地 RSA 签名 token/JWKS stub；未连接真实 Keycloak，未进行完整跨版本数据库矩阵测试。
