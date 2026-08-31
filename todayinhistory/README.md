# 历史上的今天

每天获取“历史上的今天”事件，随机选取四条组成 `news_notice` 模板卡片，并通过群机器人 Webhook 推送到企业微信群。

## GitHub Actions 配置

在 GitHub 仓库的 `Settings > Secrets and variables > Actions` 中添加：

- `TODAY_IN_HISTORY_API_KEY`：聚合数据“历史上的今天”接口 key。
- `WECOM_WEBHOOK_URL`：企业微信机器人完整 Webhook 地址。测试阶段填写 testkey 对应的地址即可。

工作流默认在北京时间每天 08:00 运行。也可以在 Actions 页面手动运行：手动运行默认启用 `dry_run`，只在日志中显示内容；确认无误后取消勾选即可推送。

## 本地运行

安装依赖：

```powershell
python -m pip install -r todayinhistory/requirements.txt
```

只获取并预览，不推送：

```powershell
python todayinhistory/today_in_history.py --dry-run
```

推送到 `credentials.yaml` 中的 `testkey`：

```powershell
python todayinhistory/today_in_history.py
```

可用 `--date 2026-08-31` 指定日期。脚本优先读取环境变量，未设置时才读取本地 `credentials.yaml`；该凭据文件已被 Git 忽略，不能提交到仓库。

## 测试

```powershell
python -m unittest discover -s todayinhistory -p "test_*.py" -v
```