# AUTO-001 Technical Baseline

scene_id: AUTO-001
version: V1.2

customer_scene: 汽车内饰革水性化客户
product: HD-S303 面层
target_metric: 低温耐折
target_condition: -30℃
target_threshold: ≥5万次

mvp_goal:
客户提出新性能指标后，系统检索企业历史证据，
识别条件差异与 Evidence Gap，
给出可追溯的优先验证项。

hard_rules:
- AI不替工程师拍板
- 无证据不判断达标/不达标
- 历史条件不同不得直接外推
- 所有展示数字和关键结论必须可追溯到source/chunk
- 当前数据为脱敏模拟数据
