# 0.1.0 Packaging 验证记录

验证日期：2026-09-14。任务为 Django reusable app / Python distribution 整理。
`src/drf_unified_rbac/` 和 `example_project/` 的代码内容均未修改。
开始工作前已有 54 个文件的 Git executable-bit 差异（100755 → 100644），本次保留这些既有差异。

## 修改文件与原因

| 文件 | 修改原因 |
| --- | --- |
| `pyproject.toml` | 保留名称、0.1.0、Python 与运行时依赖范围；补充 wheel 构建依赖、build 开发依赖；仅发现 drf_unified_rbac 及子包；禁用隐式 namespace 和非代码数据自动收集。 |
| `MANIFEST.in` | 源码包收录完整 tests、pytest.ini 和 example_project 的 Python 文件，以便独立运行集成测试；排除字节码、数据库、备份和临时文件。 |
| `pytest.ini` | 删除 pythonpath 中的 src，测试必须使用已安装的 app。保留 Consumer 与测试配置的路径。 |
| `.gitignore` | 忽略 .venv-* 验证环境。 |
| `README.md` | 补充 build、wheel 安装、Consumer 设置、URL、迁移和干净环境验证；修正 demo 环境变量名称；明确 Hybrid 后续实现。 |
| `tests/test_principal_and_provider.py` | 两个旧测试改为当前 SSOUser → Principal.from_user 路径，保留角色提取、去重和缺省角色断言。 |
| `tests/conftest.py`、`tests/test_keycloak_authentication.py`、`tests/test_me.py` | 用 timezone.utc 替代 Python 3.11 才提供的 datetime.UTC，使测试代码与声明的 Python >=3.10 对齐。 |
| `PACKAGING_VALIDATION.md` | 保存本次实际执行结果及限制。 |

## 最终结构

```text
drf-unified-rbac/
├── pyproject.toml
├── MANIFEST.in
├── README.md
├── PACKAGING_VALIDATION.md
├── pytest.ini
├── .gitignore
├── src/drf_unified_rbac/
│   ├── __init__.py
│   ├── apps.py
│   ├── admin.py
│   ├── conf.py
│   ├── urls.py
│   ├── views.py
│   ├── authentication/
│   ├── domain/
│   ├── factories/
│   ├── models/
│   ├── permissions/
│   ├── providers/
│   ├── repositories/
│   ├── services/
│   └── migrations/             # __init__.py、0001_initial.py
├── tests/
├── example_project/
│   ├── manage.py
│   ├── config/
│   └── demo/
└── dist/                       # 构建产物，Git 忽略
    ├── drf_unified_rbac-0.1.0-py3-none-any.whl
    └── drf_unified_rbac-0.1.0.tar.gz
```

临时验证环境为 `.venv-package-test/`，临时 Consumer、测试副本及核验脚本位于
`build/package-validation/`，两者均被 Git 忽略。副本只复制现有 Python 文件与 pytest.ini，
没有 src、数据库或虚拟环境；原 example_project/db.sqlite3 的 SHA-256 在验证前后相同。

## pyproject.toml 与依赖

- Backend：`setuptools.build_meta`；隔离构建依赖 `setuptools>=68`、`wheel`。
- Distribution：`drf-unified-rbac`；import/app name：`drf_unified_rbac`；版本：`0.1.0`。
- Python：`>=3.10`，与原声明一致。
- `package-dir = {"" = "src"}`；从 src 发现 `drf_unified_rbac`、`drf_unified_rbac.*`；`namespaces = false`。
- `include-package-data = false`：当前 app 全部由 Python 模块组成；migrations 是带 __init__.py 的正常 Python 子包，无需额外 package-data glob。
- Runtime：`Django>=5.2,<6.0`、`djangorestframework>=3.17,<4.0`、`PyJWT[crypto]>=2.8,<3.0`，均沿用原范围。
- Django 支撑模型、迁移与 settings；DRF 支撑认证、权限及 API；PyJWT 的 crypto extra 提供 RS256 所需 cryptography。JWKS 使用 PyJWT 的客户端，未增加 HTTP 客户端依赖。
- Dev extra：`build>=1.0`、`pytest>=8.0`、`pytest-django>=4.8`。普通 wheel 安装不安装这些工具。
- 未增加 setup.py，未更改模型发现方式、AppConfig、migration、配置协议和公共 import。

版本兼容性核对参考：[DRF 3.17 官方发布元数据](https://pypi.org/project/djangorestframework/3.17.0/)、
[setuptools 包发现](https://setuptools.pypa.io/en/latest/userguide/package_discovery.html)、
[setuptools 数据文件](https://setuptools.pypa.io/en/latest/userguide/datafiles.html)。

## 构建与归档

通用命令：

```bash
python -m pip install build
python -m build
python -m zipfile -l dist/drf_unified_rbac-0.1.0-py3-none-any.whl
```

此机器的 python 不在 PATH，实际使用 `.venv-win/Scripts/python.exe` 执行。
最终构建使用 setuptools 84.0.0、wheel 0.48.0，先构建 sdist，再从 sdist 构建 wheel：

```text
Successfully built drf_unified_rbac-0.1.0.tar.gz and drf_unified_rbac-0.1.0-py3-none-any.whl
```

首次构建检查发现旧 egg-info 的 SOURCES.txt.bak 被收录；补充 MANIFEST 排除规则后重新构建。
最终 wheel 含 29 个 Python 模块和 4 个 dist-info 文件；源码包含 63 个文件。
所有 app Python 文件逐字节匹配工作区；源码包中的 app、tests、example_project、README 和构建配置亦逐字节匹配。

wheel 包含 authentication、domain、factories、models、permissions、providers、repositories、services，
以及 migrations/__init__.py 和 migrations/0001_initial.py。所有 Python 包都具备 __init__.py。
wheel 不含 example_project、tests、db.sqlite3、.venv、.git、__pycache__、.pytest_cache、IDE 或临时文件。
sdist 包含供开发者运行的 Consumer 和测试，但它们不会被安装为 Python package。

- `drf_unified_rbac-0.1.0-py3-none-any.whl`：20178 bytes；SHA-256 `59aa6bc447c4b27aa9eb810bce81893a037c78289f11b3d2f8c5ff8011804a1d`。
- `drf_unified_rbac-0.1.0.tar.gz`：27758 bytes；SHA-256 `d035a8c360e91c62618b2b286b76ef4ad0b0b660887b9f3e5c1bf9881716a014`。

## 干净环境安装与 Django 验证

实际新建 `.venv-package-test`，`include-system-site-packages = false`，然后仅安装最终 wheel：

```powershell
& ./.venv-win/Scripts/python.exe -m venv .venv-package-test
& ./.venv-package-test/Scripts/python.exe -m pip install ./dist/drf_unified_rbac-0.1.0-py3-none-any.whl
& ./.venv-package-test/Scripts/python.exe -m pip show drf-unified-rbac
& ./.venv-package-test/Scripts/python.exe -m pip check
```

安装时自动解析的实际版本：Python 3.12.14、Django 5.2.17、DRF 3.18.1、PyJWT 2.14.0、cryptography 50.0.1。
在加入测试工具之前，已确认 pytest 和 build 不存在，并完成两种 Consumer 模式的集成检查。
`direct_url.json` 指向最终 wheel，其归档 SHA-256 与本次产物一致，无 editable 安装。

```text
Name: drf-unified-rbac
Version: 0.1.0
Location: E:\code\drf-unified-rbac\.venv-package-test\Lib\site-packages
Import: E:\code\drf-unified-rbac\.venv-package-test\Lib\site-packages\drf_unified_rbac\__init__.py
No broken requirements found.
```

| 验证 | 实际结果 |
| --- | --- |
| 独立模式 `python -I` import | 从 clean venv 的 site-packages 导入；版本和 wheel 元数据一致。 |
| 全部子模块导入 | 28 个子模块导入成功（加根模块共 29）。 |
| 公共 API | authentication.KeycloakAuthentication 和 permissions.RBACPermission 均能导入，且与原内部路径指向同一类。 |
| Django app 自动发现 | INSTALLED_APPS 中仅指定 drf_unified_rbac 即选中 DrfUnifiedRbacConfig，发现四个模型。 |
| 原 example_project/manage.py check | System check identified no issues (0 silenced)。 |
| 独立副本 manage.py check | Local 和 SSO 均无问题。 |
| 独立副本 migrate --noinput | 空库执行全部迁移成功，drf_unified_rbac.0001_initial... OK。 |
| showmigrations drf_unified_rbac | [X] 0001_initial。 |
| makemigrations --check --dry-run | No changes detected。 |
| 数据库表 | drf_unified_rbac_permission、drf_unified_rbac_role、drf_unified_rbac_rolepermission、drf_unified_rbac_userrole 均存在。 |
| Local 接口 | Basic 认证 GET /api/rbac/me 返回 200；viewer 可 list，approve 返回 403；移除角色后权限为空；匿名 me 保持 403。 |
| SSO 接口 | Consumer 环境变量选中字符串配置的 KeycloakAuthentication；签名令牌的 me/list 返回 200；viewer approve 为 403，admin approve 为 200；无角色为空；错误 audience 和缺失令牌为 401；不创建本地用户。 |
| 默认 URL | reverse 返回 /api/rbac/me；库内仅保留 me，无硬编码宿主前缀。 |

接口检查使用真实 Consumer URLConf、DRF 请求处理和 RSA 签名测试令牌。
JWKS 查询使用本地 stub，未连接真实 Keycloak 服务。日志中的 Forbidden/Unauthorized 是断言预期的拒绝结果。
本次实际测试 Python 3.12.14，未执行完整 Python/Django 版本矩阵。

## 自动化测试及既有失败

改造前命令：`.venv-win/Scripts/python.exe -m pytest -q`。
结果：`2 failed, 69 passed`，错误为：

```text
AttributeError: type object 'Principal' has no attribute 'from_sso_claims'
```

失败测试为 test_principal_from_sso_claims_extracts_configured_client_roles 和
 test_missing_client_roles_returns_empty_collection。
原因是源码中的 from_sso_claims 已被注释，旧测试未更新；与本次 packaging 无关。
修复仅更新测试输入路径为 SSOUser → Principal.from_user，没有恢复、重写或修改 Principal。
修复后开发环境：`71 passed in 1.03s`。

安装最终 wheel 后单独安装 pytest 9.1.1 / pytest-django 4.14.0，清除 PYTHONPATH 和
DJANGO_SETTINGS_MODULE，在 `build/package-validation`（没有 src 目录）执行：

```powershell
& E:/code/drf-unified-rbac/.venv-package-test/Scripts/python.exe -m pytest -q
```

最终结果：`71 passed in 1.11s`；`pip check` 无依赖问题。
测试副本与仓库测试逐字节相同；验证使用的是安装后的 wheel。
`git diff --check` 通过。pip 安装测试工具时有查询 pip 最新版本失败的提示，安装本身退出码为 0，不影响测试。

## Consumer 最小接入

安装 wheel，并在普通 Django 项目的 settings.py 中增加：

```python
INSTALLED_APPS += ["rest_framework", "drf_unified_rbac"]
DRF_RBAC = {"AUTH_MODE": "local"}
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
}
```

项目 urls.py：

```python
from django.urls import include, path

urlpatterns = [path("api/rbac/", include("drf_unified_rbac.urls"))]
```

执行 `python manage.py migrate`，在现有业务 ViewSet 中使用：

```python
from rest_framework.viewsets import ModelViewSet
from drf_unified_rbac.permissions import RBACPermission

class OrderViewSet(ModelViewSet):
    # 使用业务项目自己的 queryset 和 serializer_class。
    permission_classes = [RBACPermission]
    required_permissions = {
        "list": "demo.order.view",
        "retrieve": "demo.order.view",
        "create": "demo.order.create",
    }
```

在本地 Role、Permission、RolePermission、UserRole 中配置实际授权后，
`GET /api/rbac/me` 返回当前身份、角色及权限，路径无结尾斜杠。
SSO 项目将 AUTH_MODE 改为 sso，配置 KEYCLOAK_ISSUER、KEYCLOAK_CLIENT_ID、可选
KEYCLOAK_AUDIENCE，并将认证类设置为 drf_unified_rbac.authentication.KeycloakAuthentication。
实际 demo 继续从 DRF_RBAC_AUTH_MODE / DRF_RBAC_KEYCLOAK_* 环境变量读取配置。

## 当前能力与后续范围

0.1.0 保留 Local / SSO 二选一、KeycloakAuthentication、Principal、AuthorizationService、
RBACPermission、LocalRoleProvider、SSORoleProvider、get_role_provider()、四个 RBAC 模型、
Django migrations 与 /api/rbac/me。
Hybrid 留到后续版本（例如 0.2.x），没有增加 per-principal provider resolver、release.* 权限或发布系统业务代码。
其他未实现能力继续以 README Current scope 为准。
