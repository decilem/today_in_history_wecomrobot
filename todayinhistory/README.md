# 历史上的今天

每天获取“历史上的今天”事件，按历史时期抽取五条并按年份排序，使用必应每日壁纸作为卡片图片，组成 `news_notice` 模板卡片后通过群机器人 Webhook 推送到企业微信群。由于企业微信模板卡片的 `vertical_content_list` 最多支持四项，第五条事件会追加到最后一项描述中。

## GitHub Actions 配置

在 GitHub 仓库的 `Settings > Secrets and variables > Actions` 中添加：

- `TODAY_IN_HISTORY_API_KEY`：聚合数据“历史上的今天”接口 key。
- `WECOM_WEBHOOK_URL`：企业微信机器人完整 Webhook 地址。测试阶段填写 testkey 对应的地址即可。
- `WECOM_WEBHOOK_TEST_URL`：测试环境企业微信机器人 Webhook 地址，用于手动运行时选择 `test` 环境。

工作流默认在北京时间工作日 07:49 运行并推送到正式环境。也可以在 Actions 页面手动运行，通过 `webhook_env` 选择 `production` 或 `test`；如只想在日志中预览内容，请勾选 `dry_run`。

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