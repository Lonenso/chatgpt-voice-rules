# ChatGPT Voice 自动更新规则集

从 [OpenAI 官方 JSON](https://openai.com/chatgpt-voice.json) 生成 Shadowrocket（小火箭）远程 IP 规则。无需 NAS 或自建公网服务器。

## 订阅地址

```text
https://raw.githubusercontent.com/Lonenso/chatgpt-voice-rules/main/rules/chatgpt-voice.list
```

该链接用于规则集，不是代理节点订阅。规则文件不包含代理账号、节点、密钥或策略名称。

## iPhone 配置

1. 在小火箭「配置」中备份或复制当前配置，然后点当前配置旁的 `ⓘ` →「规则」→ `+`。
2. 类型选择 `RULE-SET`，地址粘贴上面的订阅链接，策略选择支持 UDP 的节点/分组，或 `PROXY`。
3. 将它排在 GEOIP、宽泛的 IP 规则及 FINAL 之前，保存并使用配置。首页「全局路由」选择「配置」。

也可以在已有配置的 `[Rule]` 段加入这一行（不要用它覆盖整个配置）：

```ini
RULE-SET,https://raw.githubusercontent.com/Lonenso/chatgpt-voice-rules/main/rules/chatgpt-voice.list,PROXY
```

若你已有专用 ChatGPT 分组，将 `PROXY` 替换成该分组的准确名称。策略只出现在本地引用这一行，远程规则内容类似 `IP-CIDR,4.155.146.196/32,no-resolve`；未来 IPv6 使用 `IP-CIDR6`。

## 开启手机端自动更新

- 在小火箭的「设置 → 配置」中开启「自动后台更新」，更新间隔选择 1 天。不同版本的菜单名称可能略有差异。
- 在 iOS「设置 → 通用 → 后台 App 刷新」允许 Shadowrocket 后台刷新。
- 需要立即刷新时，点击当前配置 →「使用配置」或「编译配置」，刷新所引用的远程资源。
- 如果主配置也是远程订阅，直接在其中添加的规则可能被主配置更新覆盖。可以使用本地副本并移除副本中的 `update-url`，或者使用小火箭的扩展/包含配置保留本地更改。本地配置仍可自动更新引用的远程规则集。

iOS 决定后台任务的实际运行时间，不能保证每 24 小时准点刷新。强制退出应用后后台任务可能不运行，可重新打开并手动编译配置。

## 自动更新与故障保护

- GitHub Actions 每 6 小时检查官方数据一次，计划时间为北京时间 02:17、08:17、14:17、20:17；GitHub 可能延迟或漏掉某次定时任务。
- 按官方结构读取 `prefixes[].ipv4Prefix` 和 `prefixes[].ipv6Prefix`；严格验证 CIDR、地址族、公共地址及非空列表，拒绝重复 JSON 字段、默认路由和不完整/无效内容。
- 规范化、去重和排序，不扩大或合并网段。只有 CIDR 集合变化时更新文件并提交；源数据的时间戳、顺序、重复项变化不会制造提交。
- 下载最多重试 3 次，单次超时 30 秒。先完整校验，再原子替换文件。下载、测试、解析或校验失败时任务失败，不提交、不发布，订阅地址继续提供上次成功版本。
- 同一时刻只运行一个更新任务；遇到并发的人工提交时不强推，下次重新检查。
- 使用 GitHub 提供的短期 `GITHUB_TOKEN`，无需个人令牌。更新任务只要求 `contents: write`；独立的续用任务只要求 `actions: write`。
- GitHub 公共仓库的定时任务可能在 60 天无活动后被停用。续用任务调用 GitHub 的 workflow enable API，采用无需空提交的保活方式。这一防停用效果基于现有平台行为，不属于 GitHub 长期服务保证；若将来失效，可在 Actions 手动启用任务。

## 检查运行效果

[查看自动更新运行记录](https://github.com/Lonenso/chatgpt-voice-rules/actions/workflows/update-rules.yml)。绿色表示最近运行成功；规则文件的提交时间表示最后一次 IP 变化，不表示最后检查时间。可在 Actions → Update ChatGPT Voice rules → Run workflow 立即检查。

在 iPhone 开启语音后，查看小火箭连接记录：匹配本规则集的目标 IP、UDP 3478、所选代理策略，并观察是否有双向数据。规则集只补充 Voice IP 分流；现有 ChatGPT 域名/登录规则仍需要正常工作。节点必须支持 UDP，IP 命中规则不等于网络或语音连接成功。

该规则集按官方 IP 范围匹配，不限制端口；也能覆盖这些地址的 TCP 443 连接。它不能识别同一 IP 上其他服务。官方说明语音优先使用 UDP 3478，无法使用 UDP 时可使用 TCP 443。

## 本地运行

Python 3.11 或更新版本，无第三方 Python 依赖：

```sh
python -m unittest discover -s tests -v
python scripts/update_rules.py
```

如果迁移到其他 GitHub 账号或分支，请同步修改订阅地址和示例。

## 参考

- [OpenAI 网络说明](https://help.openai.com/en/articles/9247338-network-recommendations-for-chatgpt-errors-on-web-and-apps)
- [Shadowrocket 社区手册原仓库](https://github.com/LOWERTOP/Shadowrocket)（添加规则集与自动更新操作参考）
- [GitHub 定时任务说明](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
- [GitHub workflow enable API](https://docs.github.com/en/rest/actions/workflows#enable-a-workflow)
- [无空提交保活方式的实现参考](https://github.com/liskin/gh-workflow-keepalive)
