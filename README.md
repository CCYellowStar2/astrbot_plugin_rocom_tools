# astrbot_plugin_rocom_tools

## 简介
一个 [AstrBot](https://github.com/Soulter/AstrBot) 插件，提供洛克王国世界相关查询工具，当前支持：

- 精灵 Wiki 查询
- 技能 Wiki 查询
- 生蛋配对查询
- 蛋组成员查询

插件会优先返回图片卡片；当图片渲染失败时，会自动回退为纯文本结果。

## 安装
通过 AstrBot 插件商店搜索 `astrbot_plugin_rocom_tools` 一键安装。

## 配置
请在 AstrBot 控制面板中配置：

插件管理 -> `astrbot_plugin_rocom_tools` -> 操作 -> 插件配置

可选配置项：

- `base_url`
  - Wiki 站点地址，默认使用洛克王国世界 BWIKI
- `request_timeout`
  - Wiki 请求超时时间，网络较慢时可以适当调大
- `candidate_limit`
  - Wiki 搜索候选数量
- `summary_length`
  - 文本模式下摘要最大长度
- `render_as_image`
  - 是否优先返回图片卡片
- `user_agent`
  - 访问 Wiki 时使用的请求头

## 使用方法
### 精灵查询
使用：

`/精灵wiki <精灵名/别名/关键词>`

例如：

`/精灵wiki 治愈兔`

可返回精灵立绘、异色/果实/精灵蛋展示、进化链、六维、特性、克制表等信息。

### 技能查询
使用：

`/技能wiki <技能名/关键词>`

例如：

`/技能wiki 焰火`

可返回技能属性、分类、耗能、威力、技能效果与可学精灵。

### 生蛋查询
使用：

`/生蛋查询 <精灵名>`

或：

`/生蛋查询 <精灵A> <精灵B>`

例如：

`/生蛋查询 雪影娃娃`

`/生蛋查询 雪影娃娃 怒目怂猫`

单精灵查询会返回生蛋状态、蛋组、母系产蛋信息和部分父系候选；双精灵查询会判断两者能否生蛋。

### 蛋组查询
使用：

`/蛋组查询 <蛋组名>`

例如：

`/蛋组查询 龙组`

支持模糊匹配，如：

- `/蛋组查询 龙`
- `/蛋组查询 动物`

会返回对应蛋组的精灵数量与精灵列表。

## 更新日志
`v0.1.0`

- 完成精灵、技能、生蛋、蛋组四类查询能力
- 支持精灵图片卡片展示
- 生蛋与蛋组能力切换为在线 API

## 支持
[AstrBot 文档](https://astrbot.app)

[洛克王国世界 BWIKI](https://wiki.biligame.com/rocom)

[洛克王国计算器](https://roco.gptvip.chat)
