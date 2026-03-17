# 发布命令

## 前置条件

确保 `.env` 文件中已配置：
```
GITEA_USER=你的用户名
GITEA_TOKEN=你的访问令牌
GITEA_PUBLISH_URL=https://git.yinlihupo.cn/api/packages/你的用户名/pypi
```

## 发布到 Gitea PyPI

```bash
# 加载环境变量
source .env

# 构建并发布
uv build
uv publish -u "$GITEA_USER" -p "$GITEA_TOKEN" --publish-url "$GITEA_PUBLISH_URL"
```

## 信息

| 项目 | 值 |
|------|---|
| Gitea 域名 | git.yinlihupo.cn |
| 包名 | ylhp-common-feishu-sdk |
| 版本 | 见 pyproject.toml |

## 构建产物

- dist/ylhp_common_feishu_sdk-{version}.tar.gz
- dist/ylhp_common_feishu_sdk-{version}-py3-none-any.whl
