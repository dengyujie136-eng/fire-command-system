# 成员乙视觉火情确认优化 v1

## 优化后的链路

```text
甲的候选点与原始cluster_id
  -> 全局影像目录
  -> 候选点-影像时空质量匹配
  -> 灾前/灾中/灾后裁剪
  -> Qwen多时相联合分析 + 专业检测
  -> 热异常/聚类/视觉/检测/变化/影像质量融合
  -> 版本化确认火点
```

## 甲乙聚类边界

候选合同在保持 `fire.hotspot.candidate.v0.1` 兼容的同时，新增可选字段：

- `source_cluster_id`
- `cluster_point_count`
- `cluster_mean_confidence`
- `cluster_max_frp_mw`

这些字段存在时，乙按 `source_cluster_id` 直接复用甲的聚类，返回的 `selection_method` 为 `upstream_cluster_v1`；只有旧事件没有聚类信息时才执行乙侧兼容性时空聚类。

## 数据库

乙模块由7张表扩展为10张表。新增：

- `imagery_catalog`：事件级可复用影像目录。
- `candidate_imagery_matches`：候选点与影像的空间、时间、云量、有效像元、分辨率评分。
- `evidence_fusion_runs`：六项证据分、权重、总分、判定与规则版本。

`visual_verification_cases`新增甲聚类编号和统计字段。PostgreSQL启动时以幂等DDL补齐旧数据库字段。

关键空间对象增加PostGIS生成列与GiST索引：

- `visual_verification_cases.location_geom`
- `fire_confirmations.location_geom`
- `imagery_catalog.footprint_geom`
- `visual_image_derivatives.extent_geom`
- `visual_findings.finding_geom`

## 自动影像匹配

候选导入时会自动登记影像目录并写入匹配记录。当前评分为：

```text
0.35 * 空间覆盖
+ 0.30 * 时间匹配
+ 0.15 * 云量质量
+ 0.10 * 有效像元比例
+ 0.10 * 空间分辨率
```

缺少元数据不会伪造成满分，而是使用中性分并记录 `spatial_coverage_unverified`、`temporal_match_limited` 等原因。

## 多证据融合

每次完整复核均生成 `evidence_fusion_runs`：

```text
0.30 * FIRMS热异常
+ 0.20 * 上游聚类稳定性
+ 0.20 * Qwen视觉结果
+ 0.10 * 专业检测
+ 0.10 * 多时相变化
+ 0.10 * 影像匹配与质量
```

融合结果区分 `confirmed_strict`、`confirmed_thermal`、`uncertain` 和 `rejected`。课程展示自动确认仍保持兼容，但其最终置信度会吸收融合分，并在 `evidence_ids` 中引用 `fusion_run_id`。

## Qwen多时相输入

自动确认接口按以下顺序选择最多三种角色影像：

1. `comparison_pre`：灾前背景。
2. `primary`：灾中候选火点。
3. `comparison_post`：灾后变化。

每幅图在Qwen请求中带有时相标签。提示词要求比较灾前背景、灾中新出现的烟火证据和灾后新增火烧迹地，不能把原有裸地、云影或建筑当作本次火灾。

## 新增查询接口

```http
GET /api/visual-verification/events/{event_id}/imagery-catalog
GET /api/visual-verification/candidates/{visual_case_id}/imagery-matches
GET /api/visual-verification/candidates/{visual_case_id}/fusion-runs
```

原有给丙的接口与JSON结构保持不变：

```http
GET /api/visual-verification/events/{event_id}/confirmed-fire-points
```

