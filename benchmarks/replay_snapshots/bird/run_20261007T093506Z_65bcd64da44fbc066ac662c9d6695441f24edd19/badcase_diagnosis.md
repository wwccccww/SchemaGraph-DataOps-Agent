# 外部问数诊断

- 来源：bird
- 模型：deepseek-chat
- Prompt：text-to-sql-generic-v59
- 执行准确率：0.34
- 匹配：17
- SQL 错误：8
- 可执行率：0.84
- 方言错误率：0.0
- 上下文召回：1.0
- 引用表召回：0.9933333333333333
- 维度覆盖：1.0
- 实体覆盖：1.0
- 度量覆盖：0.972972972972973
- 结果不一致：25
- 电商规则命中用例：0
- 串库用例：0
- 这是注册库上的模型执行，不是 Gold-only，也不是官方 TPC-DS 分数。

## 未匹配

### bird_0003

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', 'base'], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:ab8f69f9f924357072d62949c521f1d2a1440943ded48a7ba51d8ec4f2606dac;2:projection_mismatch:sha256:257c017cc4b8d9cc6ce406f8b136ca1628006da7502ba486ffb046b85fa02bf6;3:projection_mismatch:sha256:65e70ddf050e9b3ed769f59c57c8cc685c54e1c38458c8789047d9225a1b4393;4:projection_mismatch:sha256:257c017cc4b8d9cc6ce406f8b136ca1628006da7502ba486ffb046b85fa02bf6;5:projection_mismatch:sha256:65e70ddf050e9b3ed769f59c57c8cc685c54e1c38458c8789047d9225a1b4393']]
- 错误类别：projection_mismatch
- 脱敏错误：projection_mismatch: FRPMPercentage 用 frpm `Percent (%) Eligible FRPM (K-12)` 小数列，不要用 Free Meal Count/Enrollment×100
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：1.0
- 度量覆盖：1.0
- 种子表：['frpm', 'schools', 'satscores']
- 引用表：['frpm', 'satscores', 'schools']
- 投影：['SchoolName', 'County', 'City', 'UnabbreviatedMailingAddress', 'Website', 'Enrollment', 'FRPMCount', 'FRPMPercentage', 'TotalSATScore', 'PerformanceCategory', 'PercentHighScorers', 'PerformanceClassification', 'OpenDate', 'SchoolStatus']
- 聚合：[]
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH base AS (
  SELECT
    s.School AS SchoolName,
    s.County AS County,
    s.City AS City,
    s.MailStreet AS UnabbreviatedMailingAddress,
    s.Website AS Website,
    f."Enrollment (K-12)" AS Enrollment,
    f."FRPM Count (K-12)" AS FRPMCount,
    ROUND(f."Free Meal Count (K-12)" * 1.0 / f."Enrollment (K-12)" * 100, 2) AS FRPMPercentage,
    (COALESCE(sat.AvgScrRead,0) + COALESCE(sat.AvgScrMath,0) + COALESCE(sat.AvgScrWrite,0)) AS TotalSATScore,
    sat.NumTstTakr,
    sat.NumGE1500,
    s.OpenDate AS OpenDate,
    s.StatusType AS SchoolStatus,
    RANK() OVER (ORDER BY f."FRPM Count (K-12)" DESC) AS frpm_rank
  FROM frpm f
  JOIN schools s ON f.CDSCode = s.CDSCode
  LEFT JOIN satscores sat ON sat.cds = s.CDSCode AND sat.rtype = 'S'
  WHERE s.Charter = 0
    AND f."Enrollment (K-12)" > 100
)
SELECT
  SchoolName,
  County,
  City,
  UnabbreviatedMailingAddress,
  Website,
  Enrollment,
  FRPMCount,
  FRPMPercentage,
  TotalSATScore,
  CASE
    WHEN NumTstTakr IS NULL THEN 'No SAT Data'
    WHEN TotalSATScore >= 1500 THEN 'High'
    WHEN TotalSATScore >= 1200 THEN 'Medium'
    ELSE 'Low'
  END AS PerformanceCategory,
  CASE WHEN NumTstTakr > 0 THEN ROUND(NumGE1500 * 100.0 / NumTstTakr, 2) END AS PercentHighScorers,
  CASE
    WHEN NumTstTakr IS NULL THEN 'No SAT Data'
    WHEN (FRPMCount * 1.0 / Enrollment) > 0.7 AND (NumGE1500 * 100.0 / NumTstTakr) > 20 THEN 'High-performing despite high FRPM'
    WHEN (FRPMCount * 1.0 / Enrollment) > 0.7 AND (NumGE1500 * 100.0 / NumTstTakr) < 10 THEN 'Low-performing despite high FRPM'
    WHEN (FRPMCount * 1.0 / Enrollment) < 0.3 AND (NumGE1500 * 100.0 / NumTstTakr) > 20 THEN 'High-performing despite low FRPM'
    WHEN (FRPMCount * 1.0 / Enrollment) < 0.3 AND (NumGE1500 * 100.0 / NumTstTakr) < 10 THEN 'Low-performing despite low FRPM'
    ELSE 'Expected performance'
  END AS PerformanceClassification,
  OpenDate,
  SchoolStatus
FROM base
WHERE frpm_rank = 1;
```

### bird_0005

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:e069170b986ff1581f06ade4608f695d8e2ddf0b0dd33aad3e747464e0689c6f;2:undefined_column:sha256:1176d19585f2c4ae4f0af77970f0535931d8f3887f76d26a6e3fe2de71ec2759;3:accepted:']]
- 错误类别：None
- 脱敏错误：None
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：1.0
- 度量覆盖：1.0
- 种子表：['schools', 'satscores', 'frpm']
- 引用表：['frpm', 'satscores', 'schools']
- 投影：['SchoolName', 'City', 'VirtualStatus', 'SchoolType', 'MathScore', 'ReadingScore', 'WritingScore', 'TotalScore', 'MathRank', 'TotalScoreRank', 'Enrollment', 'PovertyLevel', 'FRPMPercentage']
- 聚合：['rank']
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH VirtualSchools AS (SELECT s.CDSCode, s.School AS SchoolName, s.City AS City, CASE s.Virtual WHEN 'F' THEN 'Fully Virtual' WHEN 'P' THEN 'Partially Virtual' WHEN 'N' THEN 'Not Virtual' ELSE 'Unknown' END AS VirtualStatus, CASE s.Charter WHEN 1 THEN 'Charter School' ELSE 'Regular School' END AS SchoolType FROM schools AS s WHERE s.Virtual = 'F'), SATPerformance AS (SELECT ss.cds, ss.AvgScrMath AS MathScore, ss.AvgScrRead AS ReadingScore, ss.AvgScrWrite AS WritingScore, (ss.AvgScrRead + ss.AvgScrMath + ss.AvgScrWrite) AS TotalScore FROM satscores AS ss WHERE ss.rtype = 'S'), SchoolEnrollmentData AS (SELECT f.CDSCode, f."Enrollment (K-12)" AS Enrollment, f."Percent (%) Eligible FRPM (K-12)" AS frpm_rate FROM frpm AS f) SELECT v.SchoolName, v.City, v.VirtualStatus, v.SchoolType, sp.MathScore, sp.ReadingScore, sp.WritingScore, sp.TotalScore, RANK() OVER (ORDER BY sp.MathScore DESC) AS MathRank, RANK() OVER (ORDER BY sp.TotalScore DESC) AS TotalScoreRank, e.Enrollment, CASE WHEN e.frpm_rate >= 0.75 THEN 'High Poverty' WHEN e.frpm_rate >= 0.50 THEN 'Medium Poverty' WHEN e.frpm_rate >= 0.25 THEN 'Low Poverty' ELSE 'Very Low Poverty' END AS PovertyLevel, ROUND(e.frpm_rate * 100, 1) || '%' AS FRPMPercentage FROM VirtualSchools AS v LEFT JOIN SATPerformance AS sp ON sp.cds = v.CDSCode LEFT JOIN SchoolEnrollmentData AS e ON e.CDSCode = v.CDSCode WHERE sp.MathScore > 400 ORDER BY sp.TotalScore DESC, e.Enrollment DESC
```

### bird_0006

- 数据库：california_schools
- 分类：sql_error
- 细分类：circuit_breaker
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', 'sat_ranked'], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:bbe7e97f9c4bc634055f082fefb4fc4b2afd5be07bc5fe5c832ec93a0c7d55ce;2:projection_mismatch:sha256:f0baf50b727fa25711dfeaaad6f20c8f2c303563710a456e816e925706d212f7;3:no_progress:sha256:f0baf50b727fa25711dfeaaad6f20c8f2c303563710a456e816e925706d212f7']]
- 错误类别：no_progress
- 脱敏错误：修复没有改变症状，已标记 no_progress 并熔断
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：1.0
- 度量覆盖：1.0
- 种子表：['schools', 'satscores', 'frpm']
- 引用表：['frpm', 'satscores', 'schools']
- 投影：['School', 'SchoolType', 'EducationalOption', 'TestTakers', 'TotalAvgScore', 'ReadingScore', 'MathScore', 'WritingScore', 'PercentHighScorers', 'Enrollment', 'FreeReducedMealPercentage', 'StateRank', 'CountyRank', 'PovertyLevel', 'PerformanceCategory']
- 聚合：[]
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH sat_ranked AS (
  SELECT
    sc.cds,
    sc.sname,
    sc.cname,
    sc.NumTstTakr,
    sc.AvgScrRead,
    sc.AvgScrMath,
    sc.AvgScrWrite,
    sc.NumGE1500,
    sc.AvgScrRead + sc.AvgScrMath + sc.AvgScrWrite AS TotalAvgScore,
    RANK() OVER (ORDER BY sc.AvgScrRead + sc.AvgScrMath + sc.AvgScrWrite DESC) AS StateRank,
    DENSE_RANK() OVER (PARTITION BY sc.cname ORDER BY sc.AvgScrRead + sc.AvgScrMath + sc.AvgScrWrite DESC) AS CountyRank
  FROM satscores AS sc
  WHERE sc.rtype = 'S'
    AND sc.NumTstTakr > 500
)
SELECT
  s.School AS School,
  s.SOCType AS SchoolType,
  s.EdOpsName AS EducationalOption,
  sr.NumTstTakr AS TestTakers,
  sr.TotalAvgScore AS TotalAvgScore,
  sr.AvgScrRead AS ReadingScore,
  sr.AvgScrMath AS MathScore,
  sr.AvgScrWrite AS WritingScore,
  CAST(sr.NumGE1500 AS FLOAT) / NULLIF(sr.NumTstTakr, 0) * 100 AS PercentHighScorers,
  f."Enrollment (K-12)" AS Enrollment,
  f."Percent (%) Eligible FRPM (K-12)" AS FreeReducedMealPercentage,
  sr.StateRank AS StateRank,
  sr.CountyRank AS CountyRank,
  CASE
    WHEN f."Percent (%) Eligible FRPM (K-12)" > 0.75 THEN 'Very High Poverty'
    WHEN f."Percent (%) Eligible FRPM (K-12)" > 0.50 THEN 'High Poverty'
    WHEN f."Percent (%) Eligible FRPM (K-12)" > 0.25 THEN 'Moderate Poverty'
    ELSE 'Low Poverty'
  END AS PovertyLevel,
  CASE
    WHEN sr.TotalAvgScore > 1800 THEN 'Excellent'
    WHEN sr.TotalAvgScore > 1500 THEN 'Good'
    WHEN sr.TotalAvgScore > 1200 THEN 'Average'
    ELSE 'Below Average'
  END AS PerformanceCategory
FROM schools AS s
JOIN sat_ranked AS sr ON sr.cds = s.CDSCode
JOIN frpm AS f ON f.CDSCode = s.CDSCode
WHERE s.Magnet = 1
ORDER BY sr.TotalAvgScore DESC, PercentHighScorers DESC;
```

### bird_0008

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', 'ranked'], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:undefined_column:sha256:32dbbd6299ea19799accf11320b3198d2465c446aac440263702a51e299624fc;2:undefined_column:sha256:27d8cfa8dc43176cd3b7f5e8f1e182b3440b905f710d9508121cd1a510ae0674;3:projection_mismatch:sha256:6a03ff9bdb4b494c5f5d6451a99e8803ac46042b3dc06e1d8752b4e76db6f6f5;4:undefined_column:sha256:400334aae803a2ec9333b67621c1798f24c67d9a1dd95caefccd90a850a98f2b;5:projection_mismatch:sha256:6a03ff9bdb4b494c5f5d6451a99e8803ac46042b3dc06e1d8752b4e76db6f6f5']]
- 错误类别：projection_mismatch
- 脱敏错误：projection_mismatch: percent_eligible_frpm 输出 frpm 小数列本身，不要 ×100
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：1.0
- 度量覆盖：1.0
- 种子表：['frpm', 'schools', 'satscores']
- 引用表：['frpm', 'satscores', 'schools']
- 投影：['County', 'District', 'School', 'school_type', 'grade_level', 'frpm_count', 'enrollment', 'percent_eligible_frpm', 'num_sat_takers', 'percent_taking_sat', 'avg_reading', 'avg_math', 'avg_writing', 'total_avg_score', 'percent_scoring_over_1500', 'frpm_rank']
- 聚合：[]
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH base AS (
  SELECT
    frpm.CDSCode AS cds,
    frpm."County Name" AS "County",
    frpm."District Name" AS "District",
    frpm."School Name" AS "School",
    CASE schools.Charter WHEN 1 THEN 'Charter School' WHEN 0 THEN 'Non-Charter School' ELSE 'Unknown' END AS school_type,
    CASE
      WHEN schools.GSoffered LIKE '%K-12%' THEN 'K-12'
      WHEN schools.GSoffered LIKE '%High%' THEN 'High School'
      ELSE schools.GSoffered
    END AS grade_level,
    frpm."FRPM Count (K-12)" AS frpm_count,
    frpm."Enrollment (K-12)" AS enrollment,
    frpm."Percent (%) Eligible FRPM (K-12)" AS percent_eligible_frpm,
    satscores.NumTstTakr AS num_sat_takers,
    satscores.enroll12 AS sat_enroll12,
    satscores.AvgScrRead AS avg_reading,
    satscores.AvgScrMath AS avg_math,
    satscores.AvgScrWrite AS avg_writing,
    (satscores.AvgScrRead + satscores.AvgScrMath + satscores.AvgScrWrite) AS total_avg_score,
    satscores.NumGE1500 AS num_ge_1500
  FROM frpm
  JOIN schools ON frpm.CDSCode = schools.CDSCode
  LEFT JOIN satscores ON satscores.cds = schools.CDSCode AND satscores.rtype = 'S'
  WHERE frpm."Enrollment (K-12)" > 0
),
ranked AS (
  SELECT
    base.cds,
    base."County",
    base."District",
    base."School",
    base.school_type,
    base.grade_level,
    base.frpm_count,
    base.enrollment,
    base.percent_eligible_frpm,
    base.num_sat_takers,
    base.sat_enroll12,
    base.avg_reading,
    base.avg_math,
    base.avg_writing,
    base.total_avg_score,
    base.num_ge_1500,
    RANK() OVER (ORDER BY base.frpm_count DESC) AS frpm_rank
  FROM base
)
SELECT
  "County",
  "District",
  "School",
  school_type,
  grade_level,
  frpm_count,
  enrollment,
  ROUND(percent_eligible_frpm * 100, 2) AS percent_eligible_frpm,
  num_sat_takers,
  ROUND(num_sat_takers * 100.0 / sat_enroll12, 2) AS percent_taking_sat,
  avg_reading,
  avg_math,
  avg_writing,
  total_avg_score,
  ROUND(num_ge_1500 * 100.0 / num_sat_takers, 2) AS percent_scoring_over_1500,
  frpm_rank

-- truncated
```

### bird_0010

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', 'SchoolRankings'], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:8785d56217b0eb73bbd700488ab99e6014cbee6234c1f8712fa92d4ffb7211b2;2:accepted:']]
- 错误类别：None
- 脱敏错误：None
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：1.0
- 度量覆盖：1.0
- 种子表：['schools', 'satscores', 'frpm']
- 引用表：['frpm', 'satscores', 'schools']
- 投影：['SchoolName', 'County', 'City', 'GradeSpan', 'ReadingScore', 'MathScore', 'WritingScore', 'TotalSATScore', 'ReadingRank', 'FRPMCount', 'FRPMPercentage', 'Enrollment', 'PercentScoring1500Plus', 'SchoolType', 'PovertyLevel']
- 聚合：[]
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH SchoolRankings AS (SELECT s.CDSCode, s.School AS SchoolName, s.County AS County, s.City AS City, s.GSoffered AS GradeSpan, s.Charter AS Charter, ss.AvgScrRead AS ReadingScore, ss.AvgScrMath AS MathScore, ss.AvgScrWrite AS WritingScore, (ss.AvgScrRead + ss.AvgScrMath + ss.AvgScrWrite) AS TotalSATScore, ss.NumTstTakr, ss.NumGE1500, f."FRPM Count (Ages 5-17)" AS FRPMCount, f."Percent (%) Eligible FRPM (Ages 5-17)" AS FRPMPercentage, f."Enrollment (Ages 5-17)" AS Enrollment, RANK() OVER (ORDER BY ss.AvgScrRead DESC) AS ReadingRank FROM schools AS s JOIN satscores AS ss ON ss.cds = s.CDSCode JOIN frpm AS f ON f.CDSCode = s.CDSCode WHERE ss.NumTstTakr > 10) SELECT SchoolName, County, City, GradeSpan, ReadingScore, MathScore, WritingScore, TotalSATScore, ReadingRank, FRPMCount, FRPMPercentage, Enrollment, (CAST(NumGE1500 AS REAL) / NumTstTakr) AS PercentScoring1500Plus, CASE Charter WHEN 1 THEN 'Yes' WHEN 0 THEN 'No' ELSE 'Unknown' END AS SchoolType, CASE WHEN FRPMPercentage > 75 THEN 'High Poverty (>75%)' WHEN FRPMPercentage > 50 THEN 'Moderate Poverty (50-75%)' WHEN FRPMPercentage > 25 THEN 'Low Poverty (25-50%)' ELSE 'Very Low Poverty (<=25%)' END AS PovertyLevel FROM SchoolRankings WHERE ReadingRank = 1 ORDER BY ReadingScore DESC
```

### bird_0011

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:833d09178ecf1bb4ccdd4350af7c33ae9d87cbba1fc247e7aa912f6a94693406;2:projection_mismatch:sha256:e39cce4f7725e3cd2ab3049734b1445d1ae5219aa0fb718ff971912511cf64e0;3:projection_mismatch:sha256:567dc338eecacc3a4614b9846ed98ad16accefa0584446eb336fc29f2741ea88;4:projection_mismatch:sha256:e39cce4f7725e3cd2ab3049734b1445d1ae5219aa0fb718ff971912511cf64e0;5:projection_mismatch:sha256:567dc338eecacc3a4614b9846ed98ad16accefa0584446eb336fc29f2741ea88']]
- 错误类别：projection_mismatch
- 脱敏错误：projection_mismatch: 维度“county”有聚合时必须进入 GROUP BY；projection_mismatch: charter school 语义优先使用 schools 表的 Charter 字段，不要用 frpm 的 Y/N 列
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：1.0
- 实体覆盖：1.0
- 度量覆盖：1.0
- 种子表：['frpm', 'schools', 'satscores']
- 引用表：['frpm', 'satscores', 'schools']
- 投影：['CDSCode', 'School Name', 'County Name', 'TotalEnrollment', 'FRPMPercentage', 'FRPMCategory', 'IsCharterSchool', 'SATTestTakers', 'TotalSATScore', 'PercentageStudentsOver1500', 'CountyEnrollmentRank', 'CategorySATRank']
- 聚合：['rank']
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH SchoolData AS (
  SELECT
    frpm.CDSCode AS CDSCode,
    frpm."School Name" AS "School Name",
    frpm."County Name" AS "County Name",
    (COALESCE(frpm."Enrollment (K-12)",0) + COALESCE(frpm."Enrollment (Ages 5-17)",0)) AS TotalEnrollment,
    ROUND(frpm."Percent (%) Eligible FRPM (K-12)" * 100, 2) AS FRPMPercentage,
    CASE
      WHEN frpm."Percent (%) Eligible FRPM (K-12)" >= 0.75 THEN 'High FRPM'
      WHEN frpm."Percent (%) Eligible FRPM (K-12)" >= 0.50 THEN 'Medium FRPM'
      ELSE 'Low FRPM'
    END AS FRPMCategory,
    CASE frpm."Charter School (Y/N)" WHEN 1 THEN 'Yes' WHEN 0 THEN 'No' ELSE 'Unknown' END AS IsCharterSchool,
    satscores.NumTstTakr AS SATTestTakers,
    (COALESCE(satscores.AvgScrRead,0) + COALESCE(satscores.AvgScrMath,0) + COALESCE(satscores.AvgScrWrite,0)) AS TotalSATScore,
    CASE WHEN satscores.NumTstTakr > 0
         THEN ROUND(CAST(satscores.NumGE1500 AS REAL) * 100 / satscores.NumTstTakr, 2)
         ELSE NULL END AS PercentageStudentsOver1500
  FROM frpm
  JOIN schools ON frpm.CDSCode = schools.CDSCode
  LEFT JOIN satscores ON satscores.cds = schools.CDSCode AND satscores.rtype = 'S'
  WHERE frpm."Enrollment (K-12)" > 0
    AND (COALESCE(frpm."Enrollment (K-12)",0) + COALESCE(frpm."Enrollment (Ages 5-17)",0)) > 500
)
SELECT
  CDSCode,
  "School Name",
  "County Name",
  TotalEnrollment,
  FRPMPercentage,
  FRPMCategory,
  IsCharterSchool,
  SATTestTakers,
  TotalSATScore,
  PercentageStudentsOver1500,
  RANK() OVER (PARTITION BY "County Name" ORDER BY TotalEnrollment DESC) AS CountyEnrollmentRank,
  RANK() OVER (PARTITION BY FRPMCategory ORDER BY TotalSATScore DESC) AS CategorySATRank
FROM SchoolData
WHERE FRPMPercentage > 60
   OR (SATTestTakers > 0 AND PercentageStudentsOver1500 > 30)
ORDER BY "County Name", CountyEnrollmentRank, CategorySATRank;
```

### bird_0013

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', 'ranked'], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:e0c198189fa8894c6528b8e3b7598221905b1b5b009b3f4102f67bd3d1a3258c;2:projection_mismatch:sha256:03ee002b014b5c67e0b02fb326030ecdf1bbde960c2414991771b9109f0d4807;3:projection_mismatch:sha256:d0c06eff1cb92a3e85834d3756a6f36868792b544f503a0263024d16a8b657a8;4:projection_mismatch:sha256:03ee002b014b5c67e0b02fb326030ecdf1bbde960c2414991771b9109f0d4807;5:projection_mismatch:sha256:d0c06eff1cb92a3e85834d3756a6f36868792b544f503a0263024d16a8b657a8']]
- 错误类别：projection_mismatch
- 脱敏错误：projection_mismatch: Poverty Rate/Category 用 frpm Percent (%) Eligible FRPM (K-12) 小数分档
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：1.0
- 度量覆盖：1.0
- 种子表：['schools', 'satscores', 'frpm']
- 引用表：['frpm', 'satscores', 'schools']
- 投影：['SAT Excellence Rank', 'School Name', 'SAT Excellence Rate', 'High Scorers/Test Takers', 'Contact Number', 'City', 'Charter School', 'Poverty Rate', 'Poverty Category']
- 聚合：[]
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH base AS (
  SELECT
    s.School AS "School Name",
    s.Phone AS "Contact Number",
    s.City AS "City",
    CASE s.Charter WHEN 1 THEN 'Yes' WHEN 0 THEN 'No' ELSE 'Unknown' END AS "Charter School",
    f."Free Meal Count (K-12)" * 1.0 / f."Enrollment (K-12)" AS "Poverty Rate",
    CASE
      WHEN f."Free Meal Count (K-12)" * 1.0 / f."Enrollment (K-12)" > 0.75 THEN 'High Poverty'
      WHEN f."Free Meal Count (K-12)" * 1.0 / f."Enrollment (K-12)" > 0.50 THEN 'Medium Poverty'
      WHEN f."Free Meal Count (K-12)" * 1.0 / f."Enrollment (K-12)" > 0.25 THEN 'Low Poverty'
      ELSE 'Very Low Poverty'
    END AS "Poverty Category",
    sa.NumGE1500 AS "High Scorers/Test Takers",
    CAST(sa.NumGE1500 AS REAL) / sa.NumTstTakr AS "SAT Excellence Rate"
  FROM schools s
  JOIN satscores sa ON sa.cds = s.CDSCode
  JOIN frpm f ON f.CDSCode = s.CDSCode
  WHERE sa.rtype = 'S'
    AND sa.NumTstTakr > 0
    AND f."Enrollment (K-12)" > 0
    AND s.StatusType = 'Active'
),
ranked AS (
  SELECT
    *,
    RANK() OVER (ORDER BY "SAT Excellence Rate" DESC) AS "SAT Excellence Rank"
  FROM base
)
SELECT
  "SAT Excellence Rank",
  "School Name",
  "SAT Excellence Rate",
  "High Scorers/Test Takers",
  "Contact Number",
  "City",
  "Charter School",
  "Poverty Rate",
  "Poverty Category"
FROM ranked
WHERE "SAT Excellence Rank" <= 3
ORDER BY "SAT Excellence Rank"
```

### bird_0018

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'outer:ss."County Name"'], ['predicted_group_by', 'outer:"County Name"'], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:89d027db9e3284dc58d17e35fe0721fe9c7b3fbfd94a4956c2a8c03f978a4a1b;2:accepted:']]
- 错误类别：None
- 脱敏错误：None
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：1.0
- 度量覆盖：1.0
- 种子表：['schools', 'frpm', 'satscores']
- 引用表：['frpm', 'satscores', 'schools']
- 投影：['TotalSchools', 'County Name', 'AvgTestTakers', 'AvgTotalScore', 'AvgPercentScoring1500Plus', 'AvgFRPMPercentage', 'AvgSchoolAgeInYears', 'SchoolsWithUnder50Testers', 'SchoolsWith50To100Testers', 'SchoolsWith100To250Testers']
- 聚合：['count', 'avg', 'sum']
- 分组：['"County Name"']
- 电商规则：[]
- 串库表：[]

```sql
WITH fresno_charter AS (SELECT frpm.CDSCode, frpm."County Name", frpm."Percent (%) Eligible FRPM (K-12)" AS pct_frpm, schools.OpenDate, satscores.NumTstTakr, satscores.AvgScrRead, satscores.AvgScrMath, satscores.AvgScrWrite, satscores.NumGE1500 FROM frpm JOIN schools ON frpm.CDSCode = schools.CDSCode JOIN satscores ON satscores.cds = schools.CDSCode AND satscores.rtype = 'S' WHERE frpm."County Name" = 'Fresno' AND frpm."Charter Funding Type" = 'Directly funded' AND schools.Charter = 1 AND satscores.NumTstTakr <= 250) SELECT COUNT(DISTINCT CDSCode) AS TotalSchools, "County Name" AS "County Name", ROUND(AVG(NumTstTakr), 2) AS AvgTestTakers, ROUND(AVG(AvgScrRead + AvgScrMath + AvgScrWrite), 2) AS AvgTotalScore, ROUND(AVG(CAST(NumGE1500 AS REAL) * 100 / NumTstTakr), 2) AS AvgPercentScoring1500Plus, ROUND(AVG(pct_frpm) * 100, 2) AS AvgFRPMPercentage, ROUND(AVG(2026 - CAST(STRFTIME('%Y', OpenDate) AS INTEGER)), 2) AS AvgSchoolAgeInYears, SUM(CASE WHEN NumTstTakr <= 50 THEN 1 ELSE 0 END) AS SchoolsWithUnder50Testers, SUM(CASE WHEN NumTstTakr > 50 AND NumTstTakr <= 100 THEN 1 ELSE 0 END) AS SchoolsWith50To100Testers, SUM(CASE WHEN NumTstTakr > 100 AND NumTstTakr <= 250 THEN 1 ELSE 0 END) AS SchoolsWith100To250Testers FROM fresno_charter GROUP BY "County Name"
```

### bird_0019

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=3;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:b93a9373417ab7b8b603e084040fe7bf961f6d9b43d1ad40e672dd0e98f71e91;2:projection_mismatch:sha256:257c017cc4b8d9cc6ce406f8b136ca1628006da7502ba486ffb046b85fa02bf6;3:projection_mismatch:sha256:b93a9373417ab7b8b603e084040fe7bf961f6d9b43d1ad40e672dd0e98f71e91;4:projection_mismatch:sha256:257c017cc4b8d9cc6ce406f8b136ca1628006da7502ba486ffb046b85fa02bf6;5:projection_mismatch:sha256:b93a9373417ab7b8b603e084040fe7bf961f6d9b43d1ad40e672dd0e98f71e91']]
- 错误类别：projection_mismatch
- 脱敏错误：projection_mismatch: % Free/Reduced Price Meals 用 ROUND(Percent (%) Eligible FRPM (K-12)*100,2)||<literal>；projection_mismatch: Is Charter 用 frpm `Charter School (Y/N)`（Academic Year=<literal>）
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：1.0
- 度量覆盖：1.0
- 种子表：['schools', 'satscores', 'frpm']
- 引用表：['frpm', 'satscores', 'schools']
- 投影：['Top Math School', 'Phone Number', 'Website', 'Math Score', 'Reading Score', 'Writing Score', 'Total Score', 'Is Charter School', 'Enrollment', '% Free/Reduced Price Meals', 'Total Schools in SAT Dataset', 'Average Math Score Across All Schools']
- 聚合：['count', 'avg']
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH ranked AS (
  SELECT
    s.School AS "Top Math School",
    s.Phone AS "Phone Number",
    s.Website AS "Website",
    ss.AvgScrMath AS "Math Score",
    ss.AvgScrRead AS "Reading Score",
    ss.AvgScrWrite AS "Writing Score",
    (ss.AvgScrRead + ss.AvgScrMath + ss.AvgScrWrite) AS "Total Score",
    CASE s.Charter WHEN 1 THEN 'Yes' WHEN 0 THEN 'No' ELSE 'Unknown' END AS "Is Charter School",
    f."Enrollment (K-12)" AS "Enrollment",
    ROUND(f."Free Meal Count (K-12)" * 1.0 / f."Enrollment (K-12)" * 100, 2) || '%' AS "% Free/Reduced Price Meals",
    RANK() OVER (ORDER BY ss.AvgScrMath DESC) AS MathRank
  FROM schools s
  JOIN satscores ss ON ss.cds = s.CDSCode
  JOIN frpm f ON f.CDSCode = s.CDSCode
  WHERE s.StatusType = 'Active'
    AND ss.NumTstTakr >= 10
    AND ss.rtype = 'S'
    AND f."Academic Year" = '2014-2015'
    AND f."Enrollment (K-12)" > 0
)
SELECT
  r."Top Math School",
  r."Phone Number",
  r."Website",
  r."Math Score",
  r."Reading Score",
  r."Writing Score",
  r."Total Score",
  r."Is Charter School",
  r."Enrollment",
  r."% Free/Reduced Price Meals",
  (SELECT COUNT(DISTINCT cds) FROM satscores WHERE rtype = 'S') AS "Total Schools in SAT Dataset",
  (SELECT AVG(AvgScrMath) FROM satscores WHERE rtype = 'S') AS "Average Math Score Across All Schools"
FROM ranked r
WHERE r.MathRank = 1
ORDER BY r."Math Score" DESC;
```

### bird_0020

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:undefined_column:sha256:2dbddb9ba7ec44b7a6cc110d9db921ab62d5bb1f4a7f69cae81d4c3f3c8536b9;2:projection_mismatch:sha256:584769af9762212eaa5619dad3c0978388699eed92472106daddb7eea52140cb;3:projection_mismatch:sha256:e8478f1067b95efbeff971a2ff31f7d46aa6bd8fb1736bbfbb57513312dd30d0;4:projection_mismatch:sha256:519dfb17d494ad7ca76e587cf493f973ee331554d61d9d5c8ff3cf84765c6007;5:projection_mismatch:sha256:e8478f1067b95efbeff971a2ff31f7d46aa6bd8fb1736bbfbb57513312dd30d0']]
- 错误类别：projection_mismatch
- 脱敏错误：projection_mismatch: PovertyLevel 用 High<path> Poverty（frpm 小数），不要用 Not High Poverty；projection_mismatch: CharterSchools/NonCharter 用 frpm `Charter School (Y/N)`
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：1.0
- 度量覆盖：1.0
- 种子表：['schools', 'frpm', 'satscores']
- 引用表：['frpm', 'satscores', 'schools']
- 投影：['TotalSchools', 'AvgEnrollment', 'CharterSchools', 'NonCharterSchools', 'AvgFRPMPercentage', 'DistrictCount', 'AvgSATScore', 'MaxPercentAbove1500', 'LargestSchool', 'HighPovertySchools']
- 聚合：['count', 'avg', 'sum', 'max']
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH SchoolInfo AS (
  SELECT
    s.CDSCode,
    s.School,
    s.District,
    s.Charter AS CharterFlag,
    f."Enrollment (K-12)" AS Enrollment,
    f."Free Meal Count (K-12)" AS FreeMealCount,
    f."Percent (%) Eligible FRPM (K-12)" AS FRPMPct
  FROM schools s
  JOIN frpm f ON f.CDSCode = s.CDSCode
  WHERE s.County = 'Amador'
    AND s.StatusType = 'Active'
    AND f."Low Grade" = '9'
    AND f."High Grade" = '12'
),
SATData AS (
  SELECT
    sc.cds,
    sc.NumTstTakr,
    sc.NumGE1500,
    (sc.AvgScrRead + sc.AvgScrMath + sc.AvgScrWrite) AS TotalScore
  FROM satscores sc
  WHERE sc.rtype = 'S'
),
Joined AS (
  SELECT
    si.CDSCode,
    si.School,
    si.District,
    si.CharterFlag,
    si.Enrollment,
    si.FreeMealCount,
    si.FRPMPct,
    sd.NumTstTakr,
    sd.NumGE1500,
    sd.TotalScore,
    CASE
      WHEN si.FRPMPct IS NULL THEN NULL
      WHEN si.FRPMPct > 0.75 THEN 'High Poverty'
      ELSE 'Not High Poverty'
    END AS PovertyLevel,
    ROW_NUMBER() OVER (ORDER BY si.Enrollment DESC) AS EnrollmentRank
  FROM SchoolInfo si
  LEFT JOIN SATData sd ON sd.cds = si.CDSCode
)
SELECT
  COUNT(DISTINCT CDSCode) AS TotalSchools,
  ROUND(AVG(Enrollment), 2) AS AvgEnrollment,
  SUM(CASE WHEN CharterFlag = 1 THEN 1 ELSE 0 END) AS CharterSchools,
  SUM(CASE WHEN CharterFlag = 0 THEN 1 ELSE 0 END) AS NonCharterSchools,
  ROUND(AVG(CASE WHEN Enrollment > 0 THEN FreeMealCount * 1.0 / Enrollment END) * 100, 2) AS AvgFRPMPercentage,
  (SELECT COUNT(DISTINCT District) FROM SchoolInfo) AS DistrictCount,
  ROUND(AVG(TotalScore), 2) AS AvgSATScore,
  ROUND(MAX(CASE WHEN NumTstTakr > 0 THEN NumGE1500 * 100.0 / NumTstTakr END), 2) AS MaxPercentAbove1500,
  (SELECT School FROM Joined WHERE EnrollmentRank = 1) AS LargestSchool,
  SUM(CASE WHEN PovertyLevel = 'High Poverty' THEN 1 ELSE 0 END) AS HighPovertySchools
FROM Joined;
```

### bird_0021

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：grouping_grain
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'CategoryBreakdown:FreeMealCategory'], ['predicted_group_by', ''], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=3;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:c018d103ea0b75bfe03acf487edc02afeea1b9696457fabe4d91cb6255eb4cfb;2:accepted:']]
- 错误类别：None
- 脱敏错误：None
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：1.0
- 度量覆盖：1.0
- 种子表：['frpm', 'schools', 'satscores']
- 引用表：['frpm', 'satscores', 'schools']
- 投影：['TotalSchools', 'AvgFreeMeals', 'AvgTotalFRPM', 'AvgFreePercentage', 'AvgFRPMPercentage', 'CharterSchoolCount', 'NonCharterSchoolCount', 'AvgSATScore', 'SchoolsWithoutSATData', 'FreeMealCategoryBreakdown']
- 聚合：['count', 'avg', 'sum']
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH SchoolMealStats AS (SELECT f.CDSCode, f."Free Meal Count (K-12)" AS free_meals, f."FRPM Count (K-12)" AS frpm_meals, f."Enrollment (K-12)" AS enrollment, f."Free Meal Count (K-12)" * 100.0 / f."Enrollment (K-12)" AS free_pct, f."FRPM Count (K-12)" * 100.0 / f."Enrollment (K-12)" AS frpm_pct, sc.Charter AS charter, (s.AvgScrRead + s.AvgScrMath + s.AvgScrWrite) AS sat_total, CASE WHEN f."Free Meal Count (K-12)" >= 0.75 * f."Enrollment (K-12)" THEN 'Very High' WHEN f."Free Meal Count (K-12)" >= 0.50 * f."Enrollment (K-12)" THEN 'High' WHEN f."Free Meal Count (K-12)" >= 0.25 * f."Enrollment (K-12)" THEN 'Moderate' ELSE 'Low' END AS free_meal_category FROM frpm AS f JOIN schools AS sc ON f.CDSCode = sc.CDSCode LEFT JOIN satscores AS s ON s.cds = sc.CDSCode AND s.rtype = 'S' WHERE f."County Name" = 'Los Angeles' AND f."Free Meal Count (K-12)" > 500 AND f."FRPM Count (K-12)" < 700 AND f."Enrollment (K-12)" > 0), CategoryBreakdown AS (SELECT GROUP_CONCAT(free_meal_category || ': ' || cnt, ', ') AS breakdown FROM (SELECT free_meal_category, COUNT(*) AS cnt FROM SchoolMealStats GROUP BY free_meal_category)) SELECT COUNT(*) AS TotalSchools, ROUND(AVG(free_meals), 2) AS AvgFreeMeals, ROUND(AVG(frpm_meals), 2) AS AvgTotalFRPM, ROUND(AVG(free_pct), 2) AS AvgFreePercentage, ROUND(AVG(frpm_pct), 2) AS AvgFRPMPercentage, SUM(CASE WHEN charter = 1 THEN 1 ELSE 0 END) AS CharterSchoolCount, SUM(CASE WHEN charter = 0 THEN 1 ELSE 0 END) AS NonCharterSchoolCount, ROUND(AVG(sat_total), 2) AS AvgSATScore, (SELECT COUNT(*) FROM SchoolMealStats WHERE sat_total IS NULL) AS SchoolsWithoutSATData, (SELECT breakdown FROM CategoryBreakdown) AS FreeMealCategoryBreakdown FROM SchoolMealStats
```

### bird_0032

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', 'ranked'], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:undefined_column:sha256:afac1da5508fc2ca34f8258d83197415d8bb8840151f8c32ec0338761f0be750;2:projection_mismatch:sha256:03ee002b014b5c67e0b02fb326030ecdf1bbde960c2414991771b9109f0d4807;3:undefined_column:sha256:27d8cfa8dc43176cd3b7f5e8f1e182b3440b905f710d9508121cd1a510ae0674;4:accepted:']]
- 错误类别：None
- 脱敏错误：None
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：1.0
- 度量覆盖：1.0
- 种子表：['schools', 'satscores', 'frpm']
- 引用表：['frpm', 'satscores', 'schools']
- 投影：['FRPMRank', 'School', 'County', 'District', 'SOCType', 'Enrollment', 'FRPMCount', 'EligibilityRate', 'EligibilityCategory', 'SATTestTakers', 'AvgReading', 'AvgMath', 'AvgWriting', 'TotalSATScore', 'HighSATScorerRate', 'SATParticipationRate']
- 聚合：[]
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH base AS (SELECT frpm.CDSCode AS CDSCode, frpm."School Name" AS School, frpm."County Name" AS County, frpm."District Name" AS District, schools.SOCType AS SOCType, frpm."Enrollment (K-12)" AS Enrollment, frpm."FRPM Count (K-12)" AS FRPMCount, frpm."Free Meal Count (K-12)" * 1.0 / NULLIF(frpm."Enrollment (K-12)", 0) AS EligibilityRate, satscores.NumTstTakr AS SATTestTakers, satscores.AvgScrRead AS AvgReading, satscores.AvgScrMath AS AvgMath, satscores.AvgScrWrite AS AvgWriting, (satscores.AvgScrRead + satscores.AvgScrMath + satscores.AvgScrWrite) AS TotalSATScore, satscores.NumGE1500 AS NumGE1500 FROM frpm JOIN schools ON frpm.CDSCode = schools.CDSCode LEFT JOIN satscores ON satscores.cds = schools.CDSCode AND satscores.rtype = 'S' WHERE schools.SOC = '66'), ranked AS (SELECT base.CDSCode, base.School, base.County, base.District, base.SOCType, base.Enrollment, base.FRPMCount, base.EligibilityRate, base.SATTestTakers, base.AvgReading, base.AvgMath, base.AvgWriting, base.TotalSATScore, base.NumGE1500, RANK() OVER (ORDER BY base.FRPMCount DESC) AS FRPMRank FROM base) SELECT FRPMRank, School, County, District, SOCType, Enrollment, FRPMCount, ROUND(EligibilityRate * 100, 2) || '%' AS EligibilityRate, CASE WHEN EligibilityRate > 0.75 THEN 'Very High FRPM' WHEN EligibilityRate > 0.50 THEN 'High FRPM' WHEN EligibilityRate > 0.25 THEN 'Moderate FRPM' ELSE 'Low FRPM' END AS EligibilityCategory, SATTestTakers, AvgReading, AvgMath, AvgWriting, TotalSATScore, CASE WHEN SATTestTakers IS NULL OR SATTestTakers = 0 THEN NULL ELSE ROUND(NumGE1500 * 1.0 / SATTestTakers * 100, 2) || '%' END AS HighSATScorerRate, CASE WHEN Enrollment IS NULL OR Enrollment = 0 THEN NULL ELSE ROUND(SATTestTakers * 1.0 / Enrollment * 100, 2) || '%' END AS SATParticipationRate FROM ranked WHERE FRPMRank <= 5 ORDER BY FRPMRank
```

### bird_0045

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'DistrictAverages:s.District'], ['predicted_group_by', 'DistrictAverages:s.District'], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=4;predicted=3'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:28c8d150ce603e7f3b07e1025babc00081cc0ed66592bf8ad4ca1e5448014a8e;2:accepted:']]
- 错误类别：None
- 脱敏错误：None
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：1.0
- 度量覆盖：1.0
- 种子表：['frpm', 'schools', 'satscores']
- 引用表：['frpm', 'satscores', 'schools']
- 投影：['School', 'AvgScrWrite', 'AvgScrRead', 'AvgScrMath', 'TotalSATScore', 'NumTstTakr', 'Enrollment (K-12)', 'FRPMPercentage', 'WriteScoreRank', 'TotalScoreRank', 'DistrictAvgWriteScore', 'ComparisonToDistrictAvg', 'DifferenceFromDistrictAvg', 'PercentageTakingSAT']
- 聚合：['rank']
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH SchoolStats AS (SELECT s.School AS School, ss.AvgScrWrite AS AvgScrWrite, ss.AvgScrRead AS AvgScrRead, ss.AvgScrMath AS AvgScrMath, (ss.AvgScrRead + ss.AvgScrMath + ss.AvgScrWrite) AS TotalSATScore, ss.NumTstTakr AS NumTstTakr, f."Enrollment (K-12)" AS "Enrollment (K-12)", ROUND(f."Percent (%) Eligible FRPM (K-12)" * 100, 2) AS FRPMPercentage, s.District AS District FROM schools AS s JOIN satscores AS ss ON ss.cds = s.CDSCode LEFT JOIN frpm AS f ON f.CDSCode = s.CDSCode WHERE s.AdmFName1 = 'Ricci' AND s.AdmLName1 = 'Ulrich'), DistrictAverages AS (SELECT s.District AS District, AVG(ss.AvgScrWrite) AS DistrictAvgWriteScore FROM schools AS s JOIN satscores AS ss ON ss.cds = s.CDSCode GROUP BY s.District) SELECT st.School AS School, st.AvgScrWrite AS AvgScrWrite, st.AvgScrRead AS AvgScrRead, st.AvgScrMath AS AvgScrMath, st.TotalSATScore AS TotalSATScore, st.NumTstTakr AS NumTstTakr, st."Enrollment (K-12)" AS "Enrollment (K-12)", st.FRPMPercentage AS FRPMPercentage, RANK() OVER (ORDER BY st.AvgScrWrite DESC) AS WriteScoreRank, RANK() OVER (ORDER BY st.TotalSATScore DESC) AS TotalScoreRank, ROUND(da.DistrictAvgWriteScore, 2) AS DistrictAvgWriteScore, CASE WHEN st.AvgScrWrite > da.DistrictAvgWriteScore THEN 'Above District Average' WHEN st.AvgScrWrite = da.DistrictAvgWriteScore THEN 'Equal to District Average' ELSE 'Below District Average' END AS ComparisonToDistrictAvg, ROUND(st.AvgScrWrite - da.DistrictAvgWriteScore, 2) AS DifferenceFromDistrictAvg, ROUND(st.NumTstTakr * 100.0 / st."Enrollment (K-12)", 2) AS PercentageTakingSAT FROM SchoolStats AS st JOIN DistrictAverages AS da ON da.District = st.District ORDER BY WriteScoreRank
```

### bird_0055

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：response_shape
- 症状：[['missing_projections', 'Metric,Ratio'], ['extra_projections', 'ROUND(c.total_enrollment * 1.0 / NULLIF(NULLIF(h.total_enrollment, 0), 0), 4),Total Enrollment Ratio'], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', 'colusa,humboldt'], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=1;predicted=1'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:49c3e0019abe7e51cad8f06ee7af59ccce38fb94b51fd8f4da04a4447a413f02;2:projection_mismatch:sha256:9e3529258c8f3a33ac16e9b233f7f5c119c667bde517d2f51ceaa9bdbcf13b70;3:projection_mismatch:sha256:cdb1afd89e6e72a4bff75627520d4891159de0c2de08fa04bbbe832bd2a499e1;4:projection_mismatch:sha256:9e3529258c8f3a33ac16e9b233f7f5c119c667bde517d2f51ceaa9bdbcf13b70;5:projection_mismatch:sha256:cdb1afd89e6e72a4bff75627520d4891159de0c2de08fa04bbbe832bd2a499e1']]
- 错误类别：projection_mismatch
- 脱敏错误：projection_mismatch: 不要额外输出列 Total Enrollment Ratio、ROUND(c.total_enrollment * 1.0 / NULLIF(NULLIF(h.total_enrollment, 0), 0), 4)；冻结契约仅 Metric、Ratio（问句措辞冲突时以契约为准）；projection_mismatch: 口径：免费餐比例用 Free Meal Count (K-12) * 1.0 / Enrollment (K-12)；若无 FRPM 列再手算
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：1.0
- 度量覆盖：1.0
- 种子表：['frpm', 'schools', 'satscores']
- 引用表：['frpm', 'satscores', 'schools']
- 投影：['Total Enrollment Ratio', 'ROUND(c.total_enrollment * 1.0 / NULLIF(NULLIF(h.total_enrollment, 0), 0), 4)']
- 聚合：[]
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH colusa AS (
  SELECT
    COUNT(DISTINCT s.CDSCode) AS total_schools,
    COUNT(DISTINCT CASE WHEN s.Charter = 1 THEN s.CDSCode END) AS charter_schools,
    COUNT(DISTINCT CASE WHEN f."Percent (%) Eligible FRPM (K-12)" > 0.5 THEN s.CDSCode END) AS high_frpm_schools,
    AVG(sa.AvgScrRead + sa.AvgScrMath + sa.AvgScrWrite) AS avg_sat_score,
    SUM(f."FRPM Count (K-12)") AS total_frpm_students,
    SUM(f."Enrollment (K-12)") AS total_enrollment
  FROM schools s
  LEFT JOIN frpm f ON f.CDSCode = s.CDSCode
  LEFT JOIN satscores sa ON sa.cds = s.CDSCode AND sa.rtype = 'S'
  WHERE s.County = 'Colusa'
),
humboldt AS (
  SELECT
    COUNT(DISTINCT s.CDSCode) AS total_schools,
    COUNT(DISTINCT CASE WHEN s.Charter = 1 THEN s.CDSCode END) AS charter_schools,
    COUNT(DISTINCT CASE WHEN f."Percent (%) Eligible FRPM (K-12)" > 0.5 THEN s.CDSCode END) AS high_frpm_schools,
    AVG(sa.AvgScrRead + sa.AvgScrMath + sa.AvgScrWrite) AS avg_sat_score,
    SUM(f."FRPM Count (K-12)") AS total_frpm_students,
    SUM(f."Enrollment (K-12)") AS total_enrollment
  FROM schools s
  LEFT JOIN frpm f ON f.CDSCode = s.CDSCode
  LEFT JOIN satscores sa ON sa.cds = s.CDSCode AND sa.rtype = 'S'
  WHERE s.County = 'Humboldt'
)
SELECT 'Total Schools Ratio' AS Metric, ROUND(c.total_schools * 1.0 / NULLIF(h.total_schools, 0), 4) AS Ratio FROM colusa c, humboldt h
UNION ALL
SELECT 'Charter Schools Ratio', ROUND(c.charter_schools * 1.0 / NULLIF(h.charter_schools, 0), 4) FROM colusa c, humboldt h
UNION ALL
SELECT 'High FRPM Schools Ratio', ROUND(c.high_frpm_schools * 1.0 / NULLIF(h.high_frpm_schools, 0), 4) FROM colusa c, humboldt h
UNION ALL
SELECT 'Average SAT Score Ratio', ROUND(c.avg_sat_score * 1.0 / NULLIF(h.avg_sat_score, 0), 4) FROM colusa c, humboldt h
UNION ALL
SELECT 'Total FRPM Students Ratio', ROUND(c.total_frpm_students * 1.0 / NULLIF(h.total_frpm_students, 0), 4) FROM colusa c, humboldt h
UNION ALL
SELECT 'Total Enrollment Ratio', ROUND(c.total_enrollment * 1.0 / NULLIF(h.total_enrollmen
-- truncated
```

### bird_0060

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:fdfe53ed6cbd61018de4d53c2f996909f9e7d9290f50e23d45a5e111b3d6dbc1;2:accepted:']]
- 错误类别：None
- 脱敏错误：None
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：1.0
- 度量覆盖：None
- 种子表：['frpm', 'schools', 'satscores']
- 引用表：['frpm', 'satscores', 'schools']
- 投影：['SchoolName', 'Website', 'CharterNumber', 'FundingType', 'TotalEnrollment', 'FRPMCount', 'FRPMPercentage', 'PovertyLevel', 'EnrollmentRank', 'SATTestTakers', 'AvgReadingScore', 'AvgMathScore', 'AvgWritingScore', 'StudentsOver1500', 'PercentOver1500']
- 聚合：['rank']
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
SELECT schools.School AS SchoolName, schools.Website AS Website, schools.CharterNum AS CharterNumber, schools.FundingType AS FundingType, frpm."Enrollment (K-12)" AS TotalEnrollment, frpm."FRPM Count (K-12)" AS FRPMCount, ROUND(frpm."Percent (%) Eligible FRPM (K-12)" * 100, 2) || '%' AS FRPMPercentage, CASE WHEN frpm."Percent (%) Eligible FRPM (K-12)" > 0.75 THEN 'Very High Poverty' WHEN frpm."Percent (%) Eligible FRPM (K-12)" > 0.50 THEN 'High Poverty' WHEN frpm."Percent (%) Eligible FRPM (K-12)" > 0.25 THEN 'Moderate Poverty' ELSE 'Low Poverty' END AS PovertyLevel, RANK() OVER (ORDER BY frpm."Enrollment (K-12)" DESC) AS EnrollmentRank, satscores.NumTstTakr AS SATTestTakers, satscores.AvgScrRead AS AvgReadingScore, satscores.AvgScrMath AS AvgMathScore, satscores.AvgScrWrite AS AvgWritingScore, satscores.NumGE1500 AS StudentsOver1500, COALESCE(ROUND(satscores.NumGE1500 * 100.0 / NULLIF(satscores.NumTstTakr, 0), 2), 0) || '%' AS PercentOver1500 FROM schools JOIN frpm ON frpm.CDSCode = schools.CDSCode LEFT JOIN satscores ON satscores.cds = schools.CDSCode AND satscores.rtype = 'S' WHERE schools.Virtual = 'P' AND schools.Charter = 1 AND schools.County = 'San Joaquin' ORDER BY EnrollmentRank
```

### bird_0061

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:406b7dfd32a881dd3a7bd7688c322fc8484dd6b8c180b06b982a07bdfe3d80da;2:projection_mismatch:sha256:03ee002b014b5c67e0b02fb326030ecdf1bbde960c2414991771b9109f0d4807;3:projection_mismatch:sha256:406b7dfd32a881dd3a7bd7688c322fc8484dd6b8c180b06b982a07bdfe3d80da;4:projection_mismatch:sha256:03ee002b014b5c67e0b02fb326030ecdf1bbde960c2414991771b9109f0d4807;5:projection_mismatch:sha256:406b7dfd32a881dd3a7bd7688c322fc8484dd6b8c180b06b982a07bdfe3d80da']]
- 错误类别：projection_mismatch
- 脱敏错误：projection_mismatch: FRPMCount 用 frpm `FRPM Count (K-12)`，不是 Free Meal Count；projection_mismatch: FRPMPercent 用 `Percent (%) Eligible FRPM (K-12)` 小数列
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：1.0
- 度量覆盖：None
- 种子表：['frpm', 'schools', 'satscores']
- 引用表：['frpm', 'satscores', 'schools']
- 投影：['CDSCode', 'School', 'City', 'EnrollmentK12', 'FRPMCount', 'FRPMPercent', 'FRPMCategory', 'SizeRank', 'SATTestTakers', 'SATReadingScore', 'SATMathScore', 'SATWritingScore', 'SATTotalScore', 'PercentOver1500', 'SATPerformanceCategory', 'TotalCharterSchools', 'AvgCharterEnrollment']
- 聚合：['count', 'avg']
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH CharterSchoolStats AS (
  SELECT
    s.CDSCode,
    s.School,
    s.City,
    f."Enrollment (K-12)" AS EnrollmentK12,
    f."Free Meal Count (K-12)" AS FRPMCount,
    CASE WHEN f."Enrollment (K-12)" > 0
         THEN f."Free Meal Count (K-12)" * 1.0 / f."Enrollment (K-12)"
         ELSE NULL END AS FRPMPercent,
    CASE
      WHEN f."Enrollment (K-12)" > 0 AND f."Free Meal Count (K-12)" * 1.0 / f."Enrollment (K-12)" > 0.75 THEN 'High FRPM'
      WHEN f."Enrollment (K-12)" > 0 AND f."Free Meal Count (K-12)" * 1.0 / f."Enrollment (K-12)" > 0.50 THEN 'Medium FRPM'
      ELSE 'Low FRPM'
    END AS FRPMCategory,
    ROW_NUMBER() OVER (PARTITION BY s.City ORDER BY f."Enrollment (K-12)" DESC) AS SizeRank,
    sa.NumTstTakr AS SATTestTakers,
    sa.AvgScrRead AS SATReadingScore,
    sa.AvgScrMath AS SATMathScore,
    sa.AvgScrWrite AS SATWritingScore,
    (sa.AvgScrRead + sa.AvgScrMath + sa.AvgScrWrite) AS SATTotalScore,
    CASE WHEN sa.NumTstTakr > 0
         THEN sa.NumGE1500 * 1.0 / sa.NumTstTakr
         ELSE NULL END AS PercentOver1500,
    CASE
      WHEN sa.NumTstTakr IS NULL THEN 'No SAT Data'
      WHEN (sa.AvgScrRead + sa.AvgScrMath + sa.AvgScrWrite) > 1500 THEN 'High Performing'
      WHEN (sa.AvgScrRead + sa.AvgScrMath + sa.AvgScrWrite) >= 1200 THEN 'Average Performing'
      ELSE 'Low Performing'
    END AS SATPerformanceCategory
  FROM schools s
  JOIN frpm f ON f.CDSCode = s.CDSCode
  LEFT JOIN satscores sa ON sa.cds = s.CDSCode AND sa.rtype = 'S'
  WHERE s.DOC = '52'
    AND s.Charter = 1
    AND s.StatusType = 'Active'
    AND s.City = 'Hickman'
)
SELECT
  CDSCode,
  School,
  City,
  EnrollmentK12,
  FRPMCount,
  FRPMPercent,
  FRPMCategory,
  SizeRank,
  SATTestTakers,
  SATReadingScore,
  SATMathScore,
  SATWritingScore,
  SATTotalScore,
  PercentOver1500,
  SATPerformanceCategory,
  (SELECT COUNT(*) FROM CharterSchoolStats) AS TotalCharterSchools,
  (SELECT AVG(EnrollmentK12) FROM CharterSchoolStats) AS AvgCharterEnrollment
FROM CharterSchoolStats
-- truncated
```

### bird_0062

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：missing_required_table
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'CountyStats:County'], ['predicted_group_by', 'countystats:County'], ['aggregation_only_in_cte', 'countystats'], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=3;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:97215383a5cea8815aec0c9fb32fd3042665542135da8d021b1c114211498e51;2:projection_mismatch:sha256:de14716d41e28fe5d6ff57860c76f131ecac8c676ec245c08198d49f3f3ddc14;3:accepted:']]
- 错误类别：None
- 脱敏错误：None
- 上下文召回：1.0
- 引用表召回：0.6666666666666666
- 维度覆盖：None
- 实体覆盖：1.0
- 度量覆盖：1.0
- 种子表：['frpm', 'schools', 'satscores']
- 引用表：['frpm', 'schools']
- 投影：['CDSCode', 'School', 'District', 'County', 'Enrollment', 'FreeMealCount', 'FreePercentage', 'FreeCategory', 'CountyRank', 'TotalSchools', 'LowFreeSchools', 'CountyAvgFreePercent', 'PctLowFreeInCounty', 'LATotalLowFree']
- 聚合：[]
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH base AS (SELECT frpm.CDSCode AS CDSCode, frpm."School Name" AS School, frpm."District Name" AS District, frpm."County Name" AS County, frpm."Enrollment (K-12)" AS Enrollment, frpm."Free Meal Count (K-12)" AS FreeMealCount, frpm."Free Meal Count (K-12)" * 1.0 / frpm."Enrollment (K-12)" * 100 AS FreePercentage FROM frpm JOIN schools ON frpm.CDSCode = schools.CDSCode WHERE schools.Charter = 0 AND frpm."County Name" = 'Los Angeles' AND frpm."Enrollment (K-12)" > 0), lowfree AS (SELECT * FROM base WHERE FreePercentage < 0.18), countystats AS (SELECT County, COUNT(*) AS TotalSchools, SUM(CASE WHEN FreePercentage < 0.18 THEN 1 ELSE 0 END) AS LowFreeSchools, AVG(FreePercentage) AS CountyAvgFreePercent FROM base GROUP BY County) SELECT lf.CDSCode AS CDSCode, lf.School AS School, lf.District AS District, lf.County AS County, lf.Enrollment AS Enrollment, lf.FreeMealCount AS FreeMealCount, ROUND(lf.FreePercentage, 4) AS FreePercentage, CASE WHEN lf.FreePercentage < 0.06 THEN 'Very Low' WHEN lf.FreePercentage < 0.12 THEN 'Low' ELSE 'Medium' END AS FreeCategory, ROW_NUMBER() OVER (PARTITION BY lf.County ORDER BY lf.FreePercentage ASC) AS CountyRank, cs.TotalSchools AS TotalSchools, cs.LowFreeSchools AS LowFreeSchools, ROUND(cs.CountyAvgFreePercent, 4) AS CountyAvgFreePercent, ROUND(cs.LowFreeSchools * 100.0 / cs.TotalSchools, 2) || '%' AS PctLowFreeInCounty, cs.LowFreeSchools AS LATotalLowFree FROM lowfree AS lf JOIN countystats AS cs ON lf.County = cs.County ORDER BY lf.FreePercentage ASC
```

### bird_0066

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：join_semantics
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'CountyStats:County'], ['predicted_group_by', 'CountyStats:"County Name"'], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=3;predicted=3'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:80bef9fc7bcf13f9e589ff2bdc54bd2fdb5ad0f165e331868f762298b6497a9c;2:projection_mismatch:sha256:af803242d7f9b7167ea9cbda2e2688ed4af8bbe8bae3ba6398af0b389fd4d17e;3:projection_mismatch:sha256:8720d9f3deb7a87f4c8a2529af06d9435bf8e56a7837934b4ef799e21e59a51e;4:accepted:']]
- 错误类别：None
- 脱敏错误：None
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：1.0
- 度量覆盖：1.0
- 种子表：['frpm', 'schools', 'satscores']
- 引用表：['frpm', 'satscores', 'schools']
- 投影：['School', 'OpenDate', 'OpenYear', 'Enrollment', 'FRPMCount', 'FRPMPercent', 'SchoolType', 'AvgScrRead', 'AvgScrMath', 'AvgScrWrite', 'TotalSATScore', 'CountyTotalSchools', 'CountyAvgEnrollment', 'CountyAvgFRPMPercent', 'FRPMStatus', 'FRPMRank', 'SATScoreRank']
- 聚合：['rank']
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH base AS (SELECT s.School AS School, s.OpenDate AS OpenDate, STRFTIME('%Y', s.OpenDate) AS OpenYear, f."Enrollment (K-12)" AS Enrollment, f."FRPM Count (K-12)" AS FRPMCount, f."Percent (%) Eligible FRPM (K-12)" AS FRPMPercent, CASE WHEN f."Charter School (Y/N)" = 1 THEN 'Charter School' ELSE 'Non-Charter School' END AS SchoolType, ss.AvgScrRead AS AvgScrRead, ss.AvgScrMath AS AvgScrMath, ss.AvgScrWrite AS AvgScrWrite, (ss.AvgScrRead + ss.AvgScrMath + ss.AvgScrWrite) AS TotalSATScore, f."County Name" AS CountyName FROM frpm AS f JOIN schools AS s ON f.CDSCode = s.CDSCode LEFT JOIN satscores AS ss ON ss.cds = s.CDSCode AND ss.rtype = 'S' WHERE s.FundingType = 'Directly funded' AND s.County = 'Stanislaus' AND NOT s.OpenDate IS NULL AND STRFTIME('%Y', s.OpenDate) BETWEEN '2000' AND '2005' AND f."Enrollment (K-12)" > 0), CountyStats AS (SELECT "County Name" AS CountyName, COUNT(DISTINCT CDSCode) AS CountyTotalSchools, AVG("Enrollment (K-12)") AS CountyAvgEnrollment, AVG("Percent (%) Eligible FRPM (K-12)") AS CountyAvgFRPMPercent FROM frpm WHERE "County Name" = 'Stanislaus' AND "Enrollment (K-12)" > 0 GROUP BY "County Name") SELECT b.School AS School, b.OpenDate AS OpenDate, b.OpenYear AS OpenYear, b.Enrollment AS Enrollment, b.FRPMCount AS FRPMCount, b.FRPMPercent AS FRPMPercent, b.SchoolType AS SchoolType, b.AvgScrRead AS AvgScrRead, b.AvgScrMath AS AvgScrMath, b.AvgScrWrite AS AvgScrWrite, b.TotalSATScore AS TotalSATScore, c.CountyTotalSchools AS CountyTotalSchools, ROUND(c.CountyAvgEnrollment, 2) AS CountyAvgEnrollment, ROUND(c.CountyAvgFRPMPercent, 2) AS CountyAvgFRPMPercent, CASE WHEN b.FRPMPercent > c.CountyAvgFRPMPercent THEN 'Above County Average' WHEN b.FRPMPercent < c.CountyAvgFRPMPercent THEN 'Below County Average' ELSE 'At County Average' END AS FRPMStatus, RANK() OVER (ORDER BY b.FRPMPercent DESC) AS FRPMRank, RANK() OVER (ORDER BY b.TotalSATScore DESC) AS SATScoreRank FROM base AS b JOIN CountyStats AS c ON b.CountyName = c.CountyName ORDER BY b.FRPMPer
-- truncated
```

### bird_0069

- 数据库：california_schools
- 分类：sql_error
- 细分类：circuit_breaker
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=3;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:bbc8626d588f46358128f0e0cb511d2f8bc14eeff732c27d6bc1557d802ef2d9;2:no_progress:sha256:bbc8626d588f46358128f0e0cb511d2f8bc14eeff732c27d6bc1557d802ef2d9']]
- 错误类别：no_progress
- 脱敏错误：修复没有改变症状，已标记 no_progress 并熔断
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：1.0
- 度量覆盖：1.0
- 种子表：['schools', 'frpm', 'satscores']
- 引用表：['frpm', 'satscores', 'schools']
- 投影：['NCESDist', 'School', 'SchoolType', 'CurrentStatus', 'OpeningDate', 'Enrollment', 'PovertyLevel', 'AvgReadingScore', 'AvgMathScore', 'AvgWritingScore', 'AvgTotalScore', 'EnrollmentRank']
- 聚合：[]
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH base AS (
  SELECT
    s.NCESDist,
    s.School,
    CASE s.Charter WHEN 1 THEN 'Charter School' WHEN 0 THEN 'Non-Charter School' ELSE 'Unknown' END AS SchoolType,
    CASE WHEN s.ClosedDate IS NULL THEN 'Active' ELSE 'Closed' END AS CurrentStatus,
    date(s.OpenDate) AS OpeningDate,
    f."Enrollment (K-12)" AS Enrollment,
    CASE
      WHEN f."Percent (%) Eligible FRPM (K-12)" > 0.75 THEN 'High Poverty'
      WHEN f."Percent (%) Eligible FRPM (K-12)" > 0.50 THEN 'Medium Poverty'
      WHEN f."Percent (%) Eligible FRPM (K-12)" > 0.25 THEN 'Low Poverty'
      ELSE 'Very Low Poverty'
    END AS PovertyLevel,
    ss.AvgScrRead AS AvgReadingScore,
    ss.AvgScrMath AS AvgMathScore,
    ss.AvgScrWrite AS AvgWritingScore,
    ROUND((COALESCE(ss.AvgScrRead,0)+COALESCE(ss.AvgScrMath,0)+COALESCE(ss.AvgScrWrite,0))/3.0, 2) AS AvgTotalScore
  FROM schools s
  JOIN frpm f ON f.CDSCode = s.CDSCode
  LEFT JOIN satscores ss ON ss.cds = s.CDSCode AND ss.rtype = 'S'
  WHERE s.DOCType = 'State Special Schools'
    AND s.SOC LIKE '3%'
)
SELECT
  NCESDist,
  School,
  SchoolType,
  CurrentStatus,
  OpeningDate,
  Enrollment,
  PovertyLevel,
  AvgReadingScore,
  AvgMathScore,
  AvgWritingScore,
  AvgTotalScore,
  ROW_NUMBER() OVER (ORDER BY Enrollment DESC) AS EnrollmentRank
FROM base
ORDER BY EnrollmentRank ASC;
```

### bird_0077

- 数据库：california_schools
- 分类：sql_error
- 细分类：circuit_breaker
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:87747a7ff493b4eb19ed2072bfffdf471909ebd2573220dcb4cd0639ef82d64a;2:projection_mismatch:sha256:41407be8daa3accacb43e45adc805da0b1aaf0da7c693e95de19bdc27a381ec8;3:projection_mismatch:sha256:b6bac20361ad371766567d13e735895a1c02a26ed3c354da5fc0007098a4367b;4:no_progress:sha256:b6bac20361ad371766567d13e735895a1c02a26ed3c354da5fc0007098a4367b']]
- 错误类别：no_progress
- 脱敏错误：修复没有改变症状，已标记 no_progress 并熔断
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：1.0
- 度量覆盖：1.0
- 种子表：['frpm', 'schools', 'satscores']
- 引用表：['frpm', 'satscores', 'schools']
- 投影：['School', 'City', 'Percent (%) Eligible FRPM (Ages 5-17)', 'Poverty_Level', 'Is_Charter', 'Number of SAT Test Takers', 'Avg Reading Score', 'Avg Math Score', 'Avg Writing Score', 'Total SAT Score', 'SAT Ranking', 'FRPM Count', 'Enrollment']
- 聚合：['rank']
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
SELECT
  s.School AS "School",
  s.City AS "City",
  ROUND(f."Percent (%) Eligible FRPM (K-12)" * 100, 2) AS "Percent (%) Eligible FRPM (Ages 5-17)",
  CASE
    WHEN f."Percent (%) Eligible FRPM (K-12)" > 0.75 THEN 'High Poverty'
    WHEN f."Percent (%) Eligible FRPM (K-12)" > 0.50 THEN 'Medium Poverty'
    ELSE 'Low Poverty'
  END AS "Poverty_Level",
  CASE s.Charter WHEN 1 THEN 'Yes' WHEN 0 THEN 'No' ELSE 'Unknown' END AS "Is_Charter",
  sat.NumTstTakr AS "Number of SAT Test Takers",
  sat.AvgScrRead AS "Avg Reading Score",
  sat.AvgScrMath AS "Avg Math Score",
  sat.AvgScrWrite AS "Avg Writing Score",
  (sat.AvgScrRead + sat.AvgScrMath + sat.AvgScrWrite) AS "Total SAT Score",
  RANK() OVER (ORDER BY (sat.AvgScrRead + sat.AvgScrMath + sat.AvgScrWrite) DESC) AS "SAT Ranking",
  f."FRPM Count (Ages 5-17)" AS "FRPM Count",
  f."Enrollment (Ages 5-17)" AS "Enrollment"
FROM schools s
JOIN frpm f ON f.CDSCode = s.CDSCode
LEFT JOIN satscores sat ON sat.cds = s.CDSCode AND sat.rtype = 'S'
WHERE s.County = 'Los Angeles'
  AND s.GSserved = 'K-9'
  AND f."Enrollment (K-12)" > 0
ORDER BY f."Percent (%) Eligible FRPM (K-12)" DESC;
```

### bird_0078

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：join_semantics
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'outer:sbs.GSserved、sbs.school_count | SchoolsByGradeSpan:s.GSserved'], ['predicted_group_by', 'GradeSpanRank:GSserved'], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=3;predicted=3'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '']]
- 错误类别：None
- 脱敏错误：None
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：1.0
- 度量覆盖：1.0
- 种子表：['schools', 'satscores', 'frpm']
- 引用表：['frpm', 'satscores', 'schools']
- 投影：['most_common_grade_span', 'school_count', 'active_schools', 'avg_enrollment', 'total_enrollment', 'avg_frpm_percentage', 'high_poverty_schools', 'medium_poverty_schools', 'low_poverty_schools', 'avg_reading_score', 'avg_math_score', 'avg_writing_score']
- 聚合：['count', 'sum', 'avg']
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH AdelantoSchools AS (SELECT s.CDSCode, s.GSserved, s.StatusType, f."Enrollment (K-12)" AS enrollment, f."Percent (%) Eligible FRPM (K-12)" AS frpm_pct, ss.AvgScrRead, ss.AvgScrMath, ss.AvgScrWrite FROM schools AS s JOIN frpm AS f ON f.CDSCode = s.CDSCode LEFT JOIN satscores AS ss ON ss.cds = s.CDSCode AND ss.rtype = 'S' WHERE s.City = 'Adelanto' AND s.StatusType = 'Active'), GradeSpanRank AS (SELECT GSserved, COUNT(*) AS cnt, RANK() OVER (ORDER BY COUNT(*) DESC) AS grade_span_rank FROM AdelantoSchools GROUP BY GSserved), MostCommon AS (SELECT GSserved FROM GradeSpanRank WHERE grade_span_rank = 1) SELECT a.GSserved AS most_common_grade_span, COUNT(*) AS school_count, SUM(CASE WHEN a.StatusType = 'Active' THEN 1 ELSE 0 END) AS active_schools, AVG(a.enrollment) AS avg_enrollment, SUM(a.enrollment) AS total_enrollment, AVG(a.frpm_pct) AS avg_frpm_percentage, SUM(CASE WHEN a.frpm_pct > 0.75 THEN 1 ELSE 0 END) AS high_poverty_schools, SUM(CASE WHEN a.frpm_pct > 0.50 AND a.frpm_pct <= 0.75 THEN 1 ELSE 0 END) AS medium_poverty_schools, SUM(CASE WHEN a.frpm_pct <= 0.50 THEN 1 ELSE 0 END) AS low_poverty_schools, AVG(a.AvgScrRead) AS avg_reading_score, AVG(a.AvgScrMath) AS avg_math_score, AVG(a.AvgScrWrite) AS avg_writing_score FROM AdelantoSchools AS a JOIN MostCommon AS m ON m.GSserved = a.GSserved
```

### bird_0079

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'CountyStats:County'], ['predicted_group_by', 'county_stats:County'], ['aggregation_only_in_cte', 'county_stats'], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=3'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:85ed97e66fde3416f9cbe51c1866b55aeeee966d6fcc7353cdc20f95e4ce8e72;2:projection_mismatch:sha256:257c017cc4b8d9cc6ce406f8b136ca1628006da7502ba486ffb046b85fa02bf6;3:projection_mismatch:sha256:4b10be2f0cd7076d981f25cafb22c4a144ed11916fae0769f68cddf266d4e1cf;4:projection_mismatch:sha256:3e820826c67db8f8e44ae1f47ba0a46f692139f6034741e513da01819098654d;5:projection_mismatch:sha256:e79c530179cf96874b2584c9a447ca5fe1997f21dc95bc7b96e3855d6f550921']]
- 错误类别：projection_mismatch
- 脱敏错误：projection_mismatch: Charter/Regular 计数用 frpm.`Charter School (Y/N)`，不要用 schools.Charter
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：1.0
- 度量覆盖：1.0
- 种子表：['schools', 'frpm', 'satscores']
- 引用表：['frpm', 'satscores', 'schools']
- 投影：['County', 'amount', 'CharterSchools', 'RegularSchools', 'AverageEnrollment', 'HighestEnrollment', 'LowestEnrollment', 'AvgFreeReducedMealPercentage', 'AverageSATScore', 'LargestVirtualSchool']
- 聚合：[]
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH virtual_schools AS (
  SELECT
    s.CDSCode,
    s.County,
    s.School,
    s.Charter AS charter_flag,
    f."Enrollment (K-12)" AS enrollment,
    CASE WHEN f."Enrollment (K-12)" > 0
         THEN f."Free Meal Count (K-12)" * 1.0 / f."Enrollment (K-12)"
         ELSE NULL END AS free_meal_rate,
    (sa.AvgScrRead + sa.AvgScrMath + sa.AvgScrWrite) AS sat_total
  FROM schools s
  JOIN frpm f ON f.CDSCode = s.CDSCode
  LEFT JOIN satscores sa ON sa.cds = s.CDSCode AND sa.rtype = 'S'
  WHERE s.Virtual = 'F'
    AND s.County IN ('San Diego', 'Santa Barbara')
),
county_stats AS (
  SELECT
    County,
    COUNT(*) AS amount,
    SUM(CASE WHEN charter_flag = 1 THEN 1 ELSE 0 END) AS CharterSchools,
    SUM(CASE WHEN charter_flag = 0 THEN 1 ELSE 0 END) AS RegularSchools,
    AVG(enrollment) AS AverageEnrollment,
    MAX(enrollment) AS HighestEnrollment,
    MIN(enrollment) AS LowestEnrollment,
    ROUND(AVG(free_meal_rate) * 100, 2) || '%' AS AvgFreeReducedMealPercentage,
    AVG(sat_total) AS AverageSATScore,
    RANK() OVER (ORDER BY COUNT(*) DESC) AS CountyRank
  FROM virtual_schools
  GROUP BY County
),
largest AS (
  SELECT County, School AS LargestVirtualSchool,
         ROW_NUMBER() OVER (PARTITION BY County ORDER BY enrollment DESC) AS rn
  FROM virtual_schools
)
SELECT
  cs.County AS County,
  cs.amount AS amount,
  cs.CharterSchools AS CharterSchools,
  cs.RegularSchools AS RegularSchools,
  cs.AverageEnrollment AS AverageEnrollment,
  cs.HighestEnrollment AS HighestEnrollment,
  cs.LowestEnrollment AS LowestEnrollment,
  cs.AvgFreeReducedMealPercentage AS AvgFreeReducedMealPercentage,
  cs.AverageSATScore AS AverageSATScore,
  l.LargestVirtualSchool AS LargestVirtualSchool
FROM county_stats cs
JOIN largest l ON l.County = cs.County AND l.rn = 1
WHERE cs.CountyRank = 1
ORDER BY cs.amount DESC
LIMIT 1;
```

### bird_0092

- 数据库：financial
- 分类：other_result_mismatch
- 细分类：join_semantics
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'DistrictStats:d.district_id、d.A2、d.A3、d.A11 | AccountActivity:a.district_id'], ['predicted_group_by', 'DistrictStats:d.district_id、d.A3、d.A11 | AccountActivity:a.district_id'], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=5;predicted=8'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:baa26de67c7cf96558aa30b815bb3544f00ad85ca76f1d05d6aa7c8b92f369f0;2:aggregation_grain:sha256:368b3b7857ea5a5703a9edbc96a304fac27e0a5a32b525cbe5ac6924e545b845;3:aggregation_grain:sha256:6009a86b154b4e9d9e41e6a9848ac12eb4d74013ed1a13ad62ce3ae3d354ec1a;4:accepted:']]
- 错误类别：None
- 脱敏错误：None
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：None
- 度量覆盖：1.0
- 种子表：['loan', 'account', 'card', 'client', 'disp', 'district', 'order', 'trans']
- 引用表：['account', 'client', 'disp', 'district', 'loan']
- 投影：['district_count', 'total_female_clients', 'average_female_salary', 'average_female_age', 'total_female_accounts', 'total_female_loans', 'average_female_loan_amount', 'active_female_loans', 'completed_female_loans', 'defaulted_female_loans', 'regions_represented']
- 聚合：['count', 'avg', 'sum', 'group_concat']
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH DistrictStats AS (SELECT d.district_id, d.A3 AS region, d.A11 AS avg_salary, COUNT(DISTINCT c.client_id) AS female_clients, AVG(CAST(STRFTIME('%Y', '2026-10-01') AS INTEGER) - CAST(STRFTIME('%Y', c.birth_date) AS INTEGER)) AS avg_age FROM district AS d JOIN client AS c ON c.district_id = d.district_id AND c.gender = 'F' GROUP BY d.district_id, d.A3, d.A11 HAVING d.A11 BETWEEN 6000 AND 10000 AND COUNT(DISTINCT c.client_id) >= 5), AccountActivity AS (SELECT a.district_id, COUNT(l.loan_id) AS total_loans FROM account AS a JOIN disp AS dp ON dp.account_id = a.account_id AND dp.type = 'OWNER' JOIN client AS c ON c.client_id = dp.client_id AND c.gender = 'F' LEFT JOIN loan AS l ON l.account_id = a.account_id GROUP BY a.district_id), QualifiedDistricts AS (SELECT ds.district_id, ds.region, ds.avg_salary, ds.female_clients, ds.avg_age, RANK() OVER (PARTITION BY ds.region ORDER BY ds.avg_salary DESC) AS salary_rank_in_region FROM DistrictStats AS ds JOIN AccountActivity AS aa ON aa.district_id = ds.district_id WHERE aa.total_loans > 0), QualifiedClients AS (SELECT DISTINCT c.client_id, c.district_id, c.birth_date FROM client AS c JOIN QualifiedDistricts AS qd ON qd.district_id = c.district_id AND qd.salary_rank_in_region <= 3 WHERE c.gender = 'F'), QualifiedAccounts AS (SELECT DISTINCT a.account_id FROM account AS a JOIN disp AS dp ON dp.account_id = a.account_id AND dp.type = 'OWNER' JOIN QualifiedClients AS qc ON qc.client_id = dp.client_id) SELECT (SELECT COUNT(DISTINCT district_id) FROM QualifiedDistricts WHERE salary_rank_in_region <= 3) AS district_count, (SELECT COUNT(*) FROM QualifiedClients) AS total_female_clients, (SELECT AVG(avg_salary) FROM QualifiedDistricts WHERE salary_rank_in_region <= 3) AS average_female_salary, (SELECT AVG(avg_age) FROM QualifiedDistricts WHERE salary_rank_in_region <= 3) AS average_female_age, (SELECT COUNT(*) FROM QualifiedAccounts) AS total_female_accounts, (SELECT COUNT(*) FROM loan AS l JOIN QualifiedAccounts AS qa ON qa.account
-- truncated
```

### bird_0096

- 数据库：financial
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'outer:ci.gender、ci.age_group、ci.region | CustomerWeeklyStatements:T2.client_id、T1.account_id、T1.district_id、T1.date | LoanAndTransactionData:cws.client_id'], ['predicted_group_by', 'outer:cws.gender、cws.age_group、cws.region | LoanAndTransactionData:cws.client_id | CardCounts:cws.client_id'], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=7;predicted=9'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:64e07dc3bc0a05078c208b529c5f42874abe1e7fd94f286195c45e39d211d1eb;2:accepted:']]
- 错误类别：None
- 脱敏错误：None
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：1.0
- 实体覆盖：None
- 度量覆盖：None
- 种子表：['account', 'client', 'disp', 'loan', 'order', 'trans', 'card', 'district']
- 引用表：['account', 'card', 'client', 'disp', 'district', 'loan', 'trans']
- 投影：['total_weekly_owners', 'gender', 'age_group', 'region', 'avg_cards_per_customer', 'avg_loans_per_customer', 'avg_loan_amount', 'avg_transactions', 'avg_net_balance', 'customers_with_loans', 'percent_with_loans']
- 聚合：['count', 'avg', 'sum']
- 分组：['cws.gender', 'cws.age_group', 'cws.region']
- 电商规则：[]
- 串库表：[]

```sql
WITH CustomerWeeklyStatements AS (SELECT c.client_id, c.gender AS gender, CASE WHEN (CAST(STRFTIME('%Y', '2026-10-01') AS INTEGER) - CAST(STRFTIME('%Y', c.birth_date) AS INTEGER) - CASE WHEN STRFTIME('%m-%d', '2026-10-01') < STRFTIME('%m-%d', c.birth_date) THEN 1 ELSE 0 END) < 30 THEN 'Young' WHEN (CAST(STRFTIME('%Y', '2026-10-01') AS INTEGER) - CAST(STRFTIME('%Y', c.birth_date) AS INTEGER) - CASE WHEN STRFTIME('%m-%d', '2026-10-01') < STRFTIME('%m-%d', c.birth_date) THEN 1 ELSE 0 END) <= 50 THEN 'Middle-aged' ELSE 'Senior' END AS age_group, d.A3 AS region, a.account_id FROM account AS a JOIN disp AS dp ON dp.account_id = a.account_id AND dp.type = 'OWNER' JOIN client AS c ON c.client_id = dp.client_id JOIN district AS d ON d.district_id = c.district_id WHERE a.frequency = 'POPLATEK TYDNE'), LoanAndTransactionData AS (SELECT cws.client_id, COUNT(DISTINCT l.loan_id) AS loan_count, COALESCE(SUM(l.amount), 0) AS total_loan_amount, COUNT(t.trans_id) AS trans_count, COALESCE(SUM(CASE WHEN t.type = 'PRIJEM' THEN t.amount ELSE 0 END), 0) - COALESCE(SUM(CASE WHEN t.type = 'VYDAJ' THEN t.amount ELSE 0 END), 0) AS net_balance FROM CustomerWeeklyStatements AS cws LEFT JOIN loan AS l ON l.account_id = cws.account_id LEFT JOIN trans AS t ON t.account_id = cws.account_id AND t.type IN ('PRIJEM', 'VYDAJ') GROUP BY cws.client_id), CardCounts AS (SELECT cws.client_id, COUNT(DISTINCT cd.card_id) AS card_count FROM CustomerWeeklyStatements AS cws JOIN disp AS dp ON dp.account_id = cws.account_id AND dp.type = 'OWNER' LEFT JOIN card AS cd ON cd.disp_id = dp.disp_id GROUP BY cws.client_id) SELECT COUNT(DISTINCT cws.client_id) AS total_weekly_owners, cws.gender AS gender, cws.age_group AS age_group, cws.region AS region, ROUND(AVG(cc.card_count), 2) AS avg_cards_per_customer, ROUND(AVG(ltd.loan_count), 2) AS avg_loans_per_customer, ROUND(AVG(CASE WHEN ltd.loan_count > 0 THEN ltd.total_loan_amount * 1.0 / ltd.loan_count END), 2) AS avg_loan_amount, ROUND(AVG(ltd.trans_count), 2) AS avg_tr
-- truncated
```

### bird_0097

- 数据库：financial
- 分类：other_result_mismatch
- 细分类：join_semantics
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'ClientLoanInfo:d.client_id、d.type、a.frequency | ClientTransactions:d.client_id | ClientCards:d.client_id'], ['predicted_group_by', 'loan_stats:dp.client_id | trans_stats:dp.client_id | card_stats:dp.client_id'], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=8;predicted=9'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:cf9ed23a838405f2782334626c2c526add315f727864dce543091327fc8f8d85;2:accepted:']]
- 错误类别：None
- 脱敏错误：None
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：None
- 度量覆盖：None
- 种子表：['card', 'loan', 'trans', 'account', 'client', 'disp', 'district', 'order']
- 引用表：['account', 'card', 'client', 'disp', 'district', 'loan', 'trans']
- 投影：['client_id', 'gender', 'birth_date', 'district_name', 'region', 'loan_count', 'avg_loan_amount', 'active_loans', 'completed_loans', 'transaction_count', 'total_income', 'total_expense', 'net_balance', 'last_transaction_date', 'card_count', 'card_types', 'client_category', 'transaction_rank']
- 聚合：['rank']
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH disponent_po_obratu AS (SELECT DISTINCT d.client_id, a.account_id FROM disp AS d JOIN account AS a ON d.account_id = a.account_id WHERE d.type = 'DISPONENT' AND a.frequency = 'POPLATEK PO OBRATU'), client_info AS (SELECT c.client_id, c.gender, c.birth_date, di.A2 AS district_name, di.A3 AS region FROM client AS c JOIN district AS di ON c.district_id = di.district_id WHERE c.client_id IN (SELECT client_id FROM disponent_po_obratu)), loan_stats AS (SELECT dp.client_id, COUNT(l.loan_id) AS loan_count, COALESCE(ROUND(AVG(l.amount), 2), 0) AS avg_loan_amount, SUM(CASE WHEN l.status = 'A' THEN 1 ELSE 0 END) AS active_loans, SUM(CASE WHEN l.status = 'B' THEN 1 ELSE 0 END) AS completed_loans FROM disponent_po_obratu AS dp LEFT JOIN loan AS l ON l.account_id = dp.account_id GROUP BY dp.client_id), trans_stats AS (SELECT dp.client_id, COUNT(t.trans_id) AS transaction_count, COALESCE(SUM(CASE WHEN t.type = 'PRIJEM' THEN t.amount ELSE 0 END), 0) AS total_income, COALESCE(SUM(CASE WHEN t.type = 'VYDAJ' THEN t.amount ELSE 0 END), 0) AS total_expense, MAX(t.date) AS last_transaction_date FROM disponent_po_obratu AS dp LEFT JOIN trans AS t ON t.account_id = dp.account_id GROUP BY dp.client_id), card_stats AS (SELECT dp.client_id, COUNT(ca.card_id) AS card_count, GROUP_CONCAT(DISTINCT ca.type) AS card_types FROM disponent_po_obratu AS dp LEFT JOIN disp AS d2 ON d2.account_id = dp.account_id LEFT JOIN card AS ca ON ca.disp_id = d2.disp_id GROUP BY dp.client_id), combined AS (SELECT ci.client_id, ci.gender, ci.birth_date, ci.district_name, ci.region, ls.loan_count, ls.avg_loan_amount, ls.active_loans, ls.completed_loans, ts.transaction_count, ts.total_income, ts.total_expense, (ts.total_income - ts.total_expense) AS net_balance, ts.last_transaction_date, cs.card_count, cs.card_types, CASE WHEN ls.loan_count > 0 AND cs.card_count > 0 AND ts.transaction_count > 0 THEN 'Full Service Client' WHEN ls.loan_count > 0 AND cs.card_count = 0 THEN 'Loan Only Client' WHEN ls.loan_count = 0 A
-- truncated
```

### bird_0100

- 数据库：financial
- 分类：sql_error
- 细分类：circuit_breaker
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', 'client_loan_status:sfo.client_id'], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=4;predicted=5'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:b7855885e11aa94a2c4b94ded0a09daac8c1f5b2873a3bf209ed9b5f1664698b;2:no_progress:sha256:b7855885e11aa94a2c4b94ded0a09daac8c1f5b2873a3bf209ed9b5f1664698b']]
- 错误类别：no_progress
- 脱敏错误：修复没有改变症状，已标记 no_progress 并熔断
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：None
- 度量覆盖：1.0
- 种子表：['account', 'disp', 'loan', 'order', 'trans', 'card', 'client', 'district']
- 引用表：['account', 'client', 'disp', 'district', 'loan']
- 投影：['total_female_clients', 'avg_age_at_account_opening', 'clients_with_loans', 'clients_with_good_loans', 'clients_with_debt', 'earliest_account_year', 'latest_account_year']
- 聚合：['count', 'avg', 'min', 'max']
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH sokolov_female_owners AS (
  SELECT DISTINCT
    c.client_id,
    CAST(strftime('%Y', a.date) AS INTEGER) - CAST(strftime('%Y', c.birth_date) AS INTEGER) AS age_at_opening,
    CAST(strftime('%Y', a.date) AS INTEGER) AS account_year,
    a.account_id
  FROM client c
  JOIN district d ON c.district_id = d.district_id
  JOIN disp dp ON dp.client_id = c.client_id
  JOIN account a ON a.account_id = dp.account_id
  WHERE c.gender = 'F'
    AND CAST(strftime('%Y', c.birth_date) AS INTEGER) < 1950
    AND d.A2 = 'Sokolov'
    AND dp.type = 'OWNER'
),
client_loan_status AS (
  SELECT
    sfo.client_id,
    MAX(CASE WHEN l.status IN ('A','D') THEN 1 ELSE 0 END) AS has_loan,
    MAX(CASE WHEN l.status = 'A' THEN 1 ELSE 0 END) AS has_good_loan,
    MAX(CASE WHEN l.status = 'D' THEN 1 ELSE 0 END) AS has_debt
  FROM sokolov_female_owners sfo
  JOIN loan l ON l.account_id = sfo.account_id
  GROUP BY sfo.client_id
)
SELECT
  COUNT(DISTINCT sfo.client_id) AS total_female_clients,
  ROUND(AVG(sfo.age_at_opening), 2) AS avg_age_at_account_opening,
  COUNT(DISTINCT CASE WHEN cls.has_loan = 1 THEN sfo.client_id END) AS clients_with_loans,
  COUNT(DISTINCT CASE WHEN cls.has_good_loan = 1 THEN sfo.client_id END) AS clients_with_good_loans,
  COUNT(DISTINCT CASE WHEN cls.has_debt = 1 THEN sfo.client_id END) AS clients_with_debt,
  MIN(sfo.account_year) AS earliest_account_year,
  MAX(sfo.account_year) AS latest_account_year
FROM sokolov_female_owners sfo
LEFT JOIN client_loan_status cls ON cls.client_id = sfo.client_id;
```

### bird_0104

- 数据库：financial
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=5;predicted=5'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:empty_result:sha256:76875bf6b5876d91fa5a9493c76acd17ba6c818e2094b43c0b5c1fd72404ad85;2:no_progress:sha256:76875bf6b5876d91fa5a9493c76acd17ba6c818e2094b43c0b5c1fd72404ad85;3:kept_candidate:no_progress']]
- 错误类别：None
- 脱敏错误：None
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：None
- 度量覆盖：1.0
- 种子表：['loan', 'account', 'client', 'card', 'trans', 'disp', 'order', 'district']
- 引用表：['account', 'card', 'client', 'disp', 'district', 'loan', 'trans']
- 投影：['account_id', 'account_opening_date', 'transaction_date', 'days_account_open_before_transaction', 'amount', 'balance', 'district_name', 'region', 'client_id', 'gender_full', 'age_at_transaction', 'total_transactions_to_date', 'cards_issued', 'has_loan_before_transaction']
- 聚合：['count']
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH TransactionDetails AS (SELECT t.trans_id, t.account_id, t.date AS transaction_date, t.amount, t.balance, a.date AS account_opening_date, a.district_id, d.A2 AS district_name, d.A3 AS region FROM trans AS t JOIN account AS a ON t.account_id = a.account_id JOIN district AS d ON a.district_id = d.district_id WHERE t.trans_id = 840 AND t.date = '1998-10-14'), AccountOwners AS (SELECT td.trans_id, td.account_id, td.transaction_date, td.amount, td.balance, td.account_opening_date, td.district_name, td.region, c.client_id, c.gender, c.birth_date FROM TransactionDetails AS td LEFT JOIN disp AS dp ON dp.account_id = td.account_id AND dp.type = 'OWNER' LEFT JOIN client AS c ON dp.client_id = c.client_id) SELECT ao.account_id AS account_id, ao.account_opening_date AS account_opening_date, ao.transaction_date AS transaction_date, CAST((STRFTIME('%Y', ao.transaction_date) - STRFTIME('%Y', ao.account_opening_date)) * 365.25 + (STRFTIME('%m', ao.transaction_date) - STRFTIME('%m', ao.account_opening_date)) * 30.44 + (STRFTIME('%d', ao.transaction_date) - STRFTIME('%d', ao.account_opening_date)) AS INTEGER) AS days_account_open_before_transaction, ao.amount AS amount, ao.balance AS balance, ao.district_name AS district_name, ao.region AS region, ao.client_id AS client_id, CASE ao.gender WHEN 'M' THEN 'Male' WHEN 'F' THEN 'Female' ELSE 'Unknown' END AS gender_full, CAST(STRFTIME('%Y', ao.transaction_date) - STRFTIME('%Y', ao.birth_date) - CASE WHEN (STRFTIME('%m', ao.transaction_date) < STRFTIME('%m', ao.birth_date)) OR (STRFTIME('%m', ao.transaction_date) = STRFTIME('%m', ao.birth_date) AND STRFTIME('%d', ao.transaction_date) < STRFTIME('%d', ao.birth_date)) THEN 1 ELSE 0 END AS INTEGER) AS age_at_transaction, (SELECT COUNT(*) FROM trans AS t2 WHERE t2.account_id = ao.account_id AND t2.date <= ao.transaction_date) AS total_transactions_to_date, (SELECT COUNT(*) FROM card AS cd JOIN disp AS dp2 ON cd.disp_id = dp2.disp_id WHERE dp2.account_id = ao.account_id) AS cards_issued, CA
-- truncated
```

### bird_0105

- 数据库：financial
- 分类：sql_error
- 细分类：circuit_breaker
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'ClientsInDistrict:d.district_id'], ['predicted_group_by', 'clients_in_district:c.district_id | trans_stats:t.account_id'], ['aggregation_only_in_cte', 'district_info,clients_in_district,trans_stats'], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=5;predicted=5'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:4e512a1fe6c4d4702a856b0dd3e2bae3ea545db67ebf2382b1bed9f6eaa1a905;2:projection_mismatch:sha256:7e5763de39082d84afd4eb8f045a16ba98e8f5d74cabb2f0f883d54bb2ca7b6c;3:no_progress:sha256:7e5763de39082d84afd4eb8f045a16ba98e8f5d74cabb2f0f883d54bb2ca7b6c']]
- 错误类别：no_progress
- 脱敏错误：修复没有改变症状，已标记 no_progress 并熔断
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：None
- 度量覆盖：1.0
- 种子表：['account', 'loan', 'district', 'client', 'trans', 'disp', 'order', 'card']
- 引用表：['account', 'client', 'district', 'loan', 'trans']
- 投影：['district_id', 'district_name', 'region', 'account_open_date', 'days_account_open_before_loan', 'avg_salary', 'unemployment_rate_1995', 'salary_rank', 'unemployment_rank', 'num_clients', 'male_clients', 'female_clients', 'avg_client_age', 'transactions_before_loan', 'total_income_before_loan']
- 聚合：[]
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH target_loan AS (
  SELECT loan_id, account_id, date AS loan_date
  FROM loan
  WHERE date = '1994-08-25'
),
loan_account AS (
  SELECT tl.loan_id, tl.loan_date, a.account_id, a.district_id, a.date AS account_open_date
  FROM target_loan tl
  JOIN account a ON a.account_id = tl.account_id
),
district_info AS (
  SELECT d.district_id, d.A2 AS district_name, d.A3 AS region, d.A11 AS avg_salary, d.A12 AS unemployment_rate_1995,
         RANK() OVER (ORDER BY d.A11 DESC) AS salary_rank,
         RANK() OVER (ORDER BY d.A12 DESC) AS unemployment_rank
  FROM district d
),
clients_in_district AS (
  SELECT c.district_id,
         COUNT(DISTINCT c.client_id) AS num_clients,
         SUM(CASE WHEN c.gender = 'M' THEN 1 ELSE 0 END) AS male_clients,
         SUM(CASE WHEN c.gender = 'F' THEN 1 ELSE 0 END) AS female_clients,
         AVG((JULIANDAY('1994-08-25') - JULIANDAY(c.birth_date)) / 365.25) AS avg_client_age
  FROM client c
  GROUP BY c.district_id
),
trans_stats AS (
  SELECT t.account_id,
         COUNT(*) AS transactions_before_loan,
         SUM(CASE WHEN t.type = 'PRIJEM' THEN t.amount ELSE 0 END) AS total_income_before_loan
  FROM trans t
  JOIN loan_account la ON la.account_id = t.account_id
  WHERE t.date < la.loan_date
  GROUP BY t.account_id
)
SELECT la.district_id AS district_id,
       di.district_name AS district_name,
       di.region AS region,
       la.account_open_date AS account_open_date,
       CAST(JULIANDAY(la.loan_date) - JULIANDAY(la.account_open_date) AS INTEGER) AS days_account_open_before_loan,
       di.avg_salary AS avg_salary,
       di.unemployment_rate_1995 AS unemployment_rate_1995,
       di.salary_rank AS salary_rank,
       di.unemployment_rank AS unemployment_rank,
       cid.num_clients AS num_clients,
       cid.male_clients AS male_clients,
       cid.female_clients AS female_clients,
       cid.avg_client_age AS avg_client_age,
       COALESCE(ts.transactions_before_loan, 0) AS transactions_before_loan,
       COALESCE(ts.to
-- truncated
```

### bird_0111

- 数据库：financial
- 分类：other_result_mismatch
- 细分类：join_semantics
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'ClientInfo:d.account_id | AccountActivity:account_id | LoanStatus:account_id'], ['predicted_group_by', 'AccountActivity:ai.account_id | LoanStatus:ai.account_id | ClientCounts:dp.account_id'], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=5;predicted=9'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:c72b0f428ecc0b99a3fd0f290f331a8cb08ccff351fcebd6f2c9d1eb1b4fa9ef;2:accepted:']]
- 错误类别：None
- 脱敏错误：None
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：None
- 度量覆盖：None
- 种子表：['loan', 'account', 'client', 'disp', 'trans', 'order', 'card', 'district']
- 引用表：['account', 'client', 'disp', 'district', 'loan', 'trans']
- 投影：['total_accounts', 'accounts_with_multiple_clients', 'average_client_age', 'total_male_clients', 'total_female_clients', 'total_transactions_in_1996', 'total_deposits_in_1996', 'total_loans', 'avg_loan_amount', 'accounts_with_loans', 'percent_opened_q1', 'percent_opened_q2', 'percent_opened_q3', 'percent_opened_q4']
- 聚合：['count', 'sum', 'avg']
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH AccountsInLitomerice1996 AS (SELECT a.account_id, a.date AS open_date FROM account AS a JOIN district AS d ON a.district_id = d.district_id WHERE d.A2 = 'Litomerice' AND STRFTIME('%Y', a.date) = '1996'), ClientInfo AS (SELECT dp.account_id, c.client_id, c.gender, c.birth_date FROM disp AS dp JOIN client AS c ON dp.client_id = c.client_id JOIN AccountsInLitomerice1996 AS ai ON dp.account_id = ai.account_id), AccountActivity AS (SELECT ai.account_id, COUNT(t.trans_id) AS txn_count, SUM(CASE WHEN t.type = 'PRIJEM' THEN t.amount ELSE 0 END) AS deposit_amount FROM AccountsInLitomerice1996 AS ai LEFT JOIN trans AS t ON ai.account_id = t.account_id AND STRFTIME('%Y', t.date) = '1996' GROUP BY ai.account_id), LoanStatus AS (SELECT ai.account_id, COUNT(l.loan_id) AS loan_count, SUM(l.amount) AS loan_amount FROM AccountsInLitomerice1996 AS ai LEFT JOIN loan AS l ON ai.account_id = l.account_id GROUP BY ai.account_id), ClientCounts AS (SELECT dp.account_id, COUNT(DISTINCT dp.client_id) AS client_count FROM disp AS dp JOIN AccountsInLitomerice1996 AS ai ON dp.account_id = ai.account_id GROUP BY dp.account_id) SELECT COUNT(DISTINCT ai.account_id) AS total_accounts, SUM(CASE WHEN cc.client_count > 1 THEN 1 ELSE 0 END) AS accounts_with_multiple_clients, AVG(2026 - CAST(STRFTIME('%Y', ci.birth_date) AS INTEGER)) AS average_client_age, SUM(CASE WHEN ci.gender = 'M' THEN 1 ELSE 0 END) AS total_male_clients, SUM(CASE WHEN ci.gender = 'F' THEN 1 ELSE 0 END) AS total_female_clients, SUM(COALESCE(aa.txn_count, 0)) AS total_transactions_in_1996, SUM(COALESCE(aa.deposit_amount, 0)) AS total_deposits_in_1996, SUM(COALESCE(ls.loan_count, 0)) AS total_loans, AVG(ls.loan_amount) AS avg_loan_amount, SUM(CASE WHEN ls.loan_count > 0 THEN 1 ELSE 0 END) AS accounts_with_loans, ROUND(AVG(CASE WHEN CAST(STRFTIME('%m', ai.open_date) AS INTEGER) BETWEEN 1 AND 3 THEN 1 ELSE 0 END) * 100, 2) AS percent_opened_q1, ROUND(AVG(CASE WHEN CAST(STRFTIME('%m', ai.open_date) AS INTEGER) BETWEEN 4 AND 6 THEN 
-- truncated
```

### bird_0113

- 数据库：financial
- 分类：other_result_mismatch
- 细分类：response_shape
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'ClientTransactions:LC.client_id、LC.birth_date、LC.age_at_loan、d.A2、d.A3 | CardInfo:LC.client_id'], ['predicted_group_by', 'outer:lc.client_id、lc.birth_date、lc.loan_date、lc.district_name、lc.region、ci.card_count、ci.card_types | CardInfo:dp.client_id'], ['aggregation_only_in_cte', ''], ['missing_output_labels', 'None'], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=11;predicted=13'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:1f44c4f248f596c108709f3cfbd753593087941eedeb94582441c8a2fded6cce;2:join_not_on_graph:sha256:18bd12f215e6c8ffec2f7b6badf1af646c5f9713887ce326b56ace32a2895826;3:accepted:']]
- 错误类别：None
- 脱敏错误：None
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：None
- 度量覆盖：1.0
- 种子表：['card', 'client', 'loan', 'trans', 'disp', 'account', 'district', 'order']
- 引用表：['account', 'card', 'client', 'disp', 'district', 'loan', 'trans']
- 投影：['birth_date', 'age_at_loan', 'district_name', 'region', 'transaction_count', 'total_income', 'total_expense', 'expense_to_income_ratio', 'max_balance', 'min_balance', 'card_count', 'card_types', 'previous_loans']
- 聚合：['count', 'sum', 'max', 'min']
- 分组：['lc.client_id', 'lc.birth_date', 'lc.loan_date', 'lc.district_name', 'lc.region', 'ci.card_count', 'ci.card_types']
- 电商规则：[]
- 串库表：[]

```sql
WITH LoanClient AS (SELECT c.client_id, c.birth_date, d.A2 AS district_name, d.A3 AS region, l.date AS loan_date FROM loan AS l JOIN account AS a ON l.account_id = a.account_id JOIN disp AS dp ON a.account_id = dp.account_id AND dp.type = 'OWNER' JOIN client AS c ON dp.client_id = c.client_id JOIN district AS d ON c.district_id = d.district_id WHERE l.amount = 98832 AND l.date = '1996-01-03'), ClientAccounts AS (SELECT dp.client_id, a.account_id FROM disp AS dp JOIN account AS a ON dp.account_id = a.account_id JOIN LoanClient AS lc ON dp.client_id = lc.client_id), ClientTransactions AS (SELECT ca.client_id, t.type, t.amount, t.balance FROM trans AS t JOIN ClientAccounts AS ca ON t.account_id = ca.account_id JOIN LoanClient AS lc ON ca.client_id = lc.client_id WHERE t.date < lc.loan_date AND t.type IN ('PRIJEM', 'VYDAJ')), CardInfo AS (SELECT dp.client_id, GROUP_CONCAT(cd.type) AS card_types, COUNT(*) AS card_count FROM card AS cd JOIN disp AS dp ON cd.disp_id = dp.disp_id JOIN LoanClient AS lc ON dp.client_id = lc.client_id GROUP BY dp.client_id) SELECT lc.birth_date AS birth_date, CAST(STRFTIME('%Y', lc.loan_date) AS INTEGER) - CAST(STRFTIME('%Y', lc.birth_date) AS INTEGER) AS age_at_loan, lc.district_name AS district_name, lc.region AS region, COUNT(ct.amount) AS transaction_count, SUM(CASE WHEN ct.type = 'PRIJEM' THEN ct.amount ELSE 0 END) AS total_income, SUM(CASE WHEN ct.type = 'VYDAJ' THEN ct.amount ELSE 0 END) AS total_expense, ROUND(CAST(SUM(CASE WHEN ct.type = 'VYDAJ' THEN ct.amount ELSE 0 END) AS REAL) * 100.0 / NULLIF(SUM(CASE WHEN ct.type = 'PRIJEM' THEN ct.amount ELSE 0 END), 0), 2) AS expense_to_income_ratio, MAX(ct.balance) AS max_balance, MIN(ct.balance) AS min_balance, ci.card_count AS card_count, ci.card_types AS card_types, (SELECT COUNT(*) FROM loan AS l2 JOIN account AS a2 ON l2.account_id = a2.account_id JOIN disp AS dp2 ON a2.account_id = dp2.account_id WHERE dp2.client_id = lc.client_id) AS previous_loans FROM LoanClient AS lc LEFT JOIN Clien
-- truncated
```

### bird_0119

- 数据库：financial
- 分类：sql_error
- 细分类：circuit_breaker
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'AccountStats:a.account_id | ClientDetails:a.account_id | LoanInfo:a.account_id'], ['predicted_group_by', 'AccountStats:t.account_id | ClientDetails:ai.account_id | LoanInfo:ai.account_id'], ['aggregation_only_in_cte', 'AccountStats,ClientDetails,LoanInfo'], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=8;predicted=8'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:0e94716b4e3f818fc1013db4aa899098afa363d5b734b83db9d811dcb85628ef;2:projection_mismatch:sha256:2013c7cd838e3f3a287fe3ca8b37670ebf77877d40939671de35ef755caa9a3f;3:no_progress:sha256:2013c7cd838e3f3a287fe3ca8b37670ebf77877d40939671de35ef755caa9a3f']]
- 错误类别：no_progress
- 脱敏错误：修复没有改变症状，已标记 no_progress 并熔断
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：None
- 度量覆盖：None
- 种子表：['client', 'district', 'loan', 'card', 'disp', 'trans', 'account', 'order']
- 引用表：['account', 'client', 'disp', 'district', 'loan', 'trans']
- 投影：['account_id', 'district_name', 'district_region', 'urbanization_category', 'transaction_count', 'net_cash_flow', 'balance_volatility', 'client_count', 'owner_gender', 'avg_client_age', 'loan_count', 'total_loan_amount', 'avg_loan_duration_months', 'running_loans', 'finished_loans', 'defaulted_loans', 'risk_category']
- 聚合：[]
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH AccountsIn1993 AS (
  SELECT a.account_id, a.district_id, a.date AS account_open_date
  FROM account a
  WHERE a.frequency = 'POPLATEK PO OBRATU'
    AND STRFTIME('%Y', a.date) = '1993'
),
AccountStats AS (
  SELECT t.account_id,
         COUNT(t.trans_id) AS transaction_count,
         SUM(CASE WHEN t.type = 'PRIJEM' THEN t.amount ELSE 0 END) AS total_income,
         SUM(CASE WHEN t.type = 'VYDAJ' THEN t.amount ELSE 0 END) AS total_expense,
         MAX(t.balance) - MIN(t.balance) AS balance_volatility
  FROM trans t
  JOIN AccountsIn1993 ai ON ai.account_id = t.account_id
  WHERE t.type IN ('PRIJEM','VYDAJ')
  GROUP BY t.account_id
),
ClientDetails AS (
  SELECT ai.account_id,
         COUNT(DISTINCT c.client_id) AS client_count,
         MAX(c.gender) AS owner_gender,
         AVG((JULIANDAY(ai.account_open_date) - JULIANDAY(c.birth_date)) / 365.25) AS avg_client_age
  FROM AccountsIn1993 ai
  JOIN disp d ON d.account_id = ai.account_id
  JOIN client c ON c.client_id = d.client_id
  GROUP BY ai.account_id
),
LoanInfo AS (
  SELECT ai.account_id,
         COUNT(l.loan_id) AS loan_count,
         SUM(l.amount) AS total_loan_amount,
         AVG(l.duration) AS avg_loan_duration_months,
         SUM(CASE WHEN l.status = 'A' THEN 1 ELSE 0 END) AS running_loans,
         SUM(CASE WHEN l.status = 'B' THEN 1 ELSE 0 END) AS finished_loans,
         SUM(CASE WHEN l.status = 'C' THEN 1 ELSE 0 END) AS defaulted_loans
  FROM AccountsIn1993 ai
  LEFT JOIN loan l ON l.account_id = ai.account_id
  GROUP BY ai.account_id
)
SELECT
  ai.account_id AS account_id,
  ds.A2 AS district_name,
  ds.A3 AS district_region,
  CASE
    WHEN ds.A10 < 50000 THEN 'Rural'
    WHEN ds.A10 < 200000 THEN 'Semi-Urban'
    ELSE 'Urban'
  END AS urbanization_category,
  COALESCE(ast.transaction_count, 0) AS transaction_count,
  COALESCE(ast.total_income, 0) - COALESCE(ast.total_expense, 0) AS net_cash_flow,
  COALESCE(ast.balance_volatility, 0) AS balance_volatility,
  COALESCE(cd.client_count, 
-- truncated
```

### bird_0121

- 数据库：financial
- 分类：sql_error
- 细分类：circuit_breaker
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'TransactionStats:t.account_id | LoanInfo:l.account_id'], ['predicted_group_by', 'TransactionStats:t.account_id | LoanInfo:l.account_id'], ['aggregation_only_in_cte', 'TransactionStats,LoanInfo'], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=8;predicted=6'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:189d6e26dc1eaddb71a6865ea38aba35419c1d8554aa02addb8081edb50c8085;2:no_progress:sha256:189d6e26dc1eaddb71a6865ea38aba35419c1d8554aa02addb8081edb50c8085']]
- 错误类别：no_progress
- 脱敏错误：修复没有改变症状，已标记 no_progress 并熔断
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：None
- 度量覆盖：None
- 种子表：['account', 'loan', 'trans', 'district', 'client', 'disp', 'order', 'card']
- 引用表：['account', 'client', 'disp', 'district', 'loan', 'trans']
- 投影：['account_id', 'opening_date', 'district_name', 'region', 'gender', 'client_age', 'transaction_count', 'total_income', 'total_expense', 'net_balance', 'max_balance', 'loan_count', 'total_loan_amount', 'loan_status', 'customer_category', 'balance_rank']
- 聚合：[]
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH AccountsInPrachatice AS (
  SELECT a.account_id, a.date AS opening_date, d.A2 AS district_name, d.A3 AS region
  FROM account a
  JOIN district d ON a.district_id = d.district_id
  WHERE d.A2 = 'Prachatice'
),
OwnerInfo AS (
  SELECT ap.account_id, c.gender, c.birth_date
  FROM AccountsInPrachatice ap
  JOIN disp dp ON dp.account_id = ap.account_id AND dp.type = 'OWNER'
  JOIN client c ON dp.client_id = c.client_id
),
TransactionStats AS (
  SELECT t.account_id,
         COUNT(*) AS transaction_count,
         SUM(CASE WHEN t.type = 'PRIJEM' THEN t.amount ELSE 0 END) AS total_income,
         SUM(CASE WHEN t.type = 'VYDAJ' THEN t.amount ELSE 0 END) AS total_expense,
         MAX(t.balance) AS max_balance
  FROM trans t
  WHERE t.type IN ('PRIJEM','VYDAJ')
  GROUP BY t.account_id
),
LoanInfo AS (
  SELECT l.account_id,
         COUNT(*) AS loan_count,
         SUM(l.amount) AS total_loan_amount,
         CASE
           WHEN SUM(CASE WHEN l.status = 'C' THEN 1 ELSE 0 END) > 0 THEN 'Has Default'
           WHEN SUM(CASE WHEN l.status = 'A' THEN 1 ELSE 0 END) > 0 THEN 'Has Active Loan'
           WHEN SUM(CASE WHEN l.status = 'B' THEN 1 ELSE 0 END) > 0 THEN 'Has Completed Loan'
           ELSE 'No Loans'
         END AS loan_status
  FROM loan l
  GROUP BY l.account_id
)
SELECT
  ap.account_id AS account_id,
  ap.opening_date AS opening_date,
  ap.district_name AS district_name,
  ap.region AS region,
  oi.gender AS gender,
  CAST(STRFTIME('%Y', '2026-10-01') AS INTEGER) - CAST(STRFTIME('%Y', oi.birth_date) AS INTEGER) AS client_age,
  COALESCE(ts.transaction_count, 0) AS transaction_count,
  COALESCE(ts.total_income, 0) AS total_income,
  COALESCE(ts.total_expense, 0) AS total_expense,
  COALESCE(ts.total_income, 0) - COALESCE(ts.total_expense, 0) AS net_balance,
  COALESCE(ts.max_balance, 0) AS max_balance,
  COALESCE(li.loan_count, 0) AS loan_count,
  COALESCE(li.total_loan_amount, 0) AS total_loan_amount,
  COALESCE(li.loan_status, 'No Loans') AS loan_status,

-- truncated
```

### bird_0123

- 数据库：financial
- 分类：sql_error
- 细分类：circuit_breaker
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'LoanStatistics:account_id | TransactionSummary:account_id'], ['predicted_group_by', 'loan_stats:l.account_id | trans_summary:t.account_id'], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=5;predicted=5'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:6ad0b3b06ac94261c6b8b54802ee2fa3367aba367578020917aa2680bcfa3ec0;2:projection_mismatch:sha256:f54e8e0129131c8241e3c0e737e96fafbe9411a066307013fb2d4f08f1d46ef5;3:no_progress:sha256:f54e8e0129131c8241e3c0e737e96fafbe9411a066307013fb2d4f08f1d46ef5']]
- 错误类别：no_progress
- 脱敏错误：修复没有改变症状，已标记 no_progress 并熔断
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：None
- 度量覆盖：1.0
- 种子表：['loan', 'account', 'district', 'trans', 'order', 'client', 'disp', 'card']
- 引用表：['account', 'client', 'disp', 'district', 'loan', 'trans']
- 投影：['account_id', 'district_name', 'region_name', 'max_loan_amount', 'avg_loan_amount', 'loan_count', 'gender', 'age', 'income_category', 'transaction_count', 'savings_ratio', 'region_loan_rank']
- 聚合：['rank']
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH
  high_salary_districts AS (
    SELECT d.district_id, d.A2 AS district_name, d.A3 AS region_name
    FROM district d
    WHERE d.A11 > (SELECT AVG(A11) FROM district)
  ),
  loan_stats AS (
    SELECT l.account_id,
           MAX(l.amount) AS max_loan_amount,
           AVG(l.amount) AS avg_loan_amount,
           COUNT(l.loan_id) AS loan_count
    FROM loan l
    GROUP BY l.account_id
    HAVING MAX(l.amount) > 300000
  ),
  trans_summary AS (
    SELECT t.account_id,
           COUNT(t.trans_id) AS transaction_count,
           SUM(CASE WHEN t.type = 'PRIJEM' THEN t.amount ELSE 0 END) AS total_income,
           SUM(CASE WHEN t.type = 'VYDAJ' THEN t.amount ELSE 0 END) AS total_expense
    FROM trans t
    WHERE t.type IN ('PRIJEM','VYDAJ')
    GROUP BY t.account_id
  ),
  owner_info AS (
    SELECT dp.account_id,
           c.gender,
           CAST(STRFTIME('%Y','2026-10-01') AS INTEGER) - CAST(STRFTIME('%Y', c.birth_date) AS INTEGER) AS age
    FROM disp dp
    JOIN client c ON dp.client_id = c.client_id
    WHERE dp.type = 'OWNER'
  )
SELECT
  a.account_id AS account_id,
  hsd.district_name AS district_name,
  hsd.region_name AS region_name,
  ls.max_loan_amount AS max_loan_amount,
  ls.avg_loan_amount AS avg_loan_amount,
  ls.loan_count AS loan_count,
  oi.gender AS gender,
  oi.age AS age,
  CASE
    WHEN ts.total_income IS NULL THEN 'Low Income'
    WHEN ts.total_income > 1000000 THEN 'High Income'
    WHEN ts.total_income > 500000 THEN 'Medium Income'
    ELSE 'Low Income'
  END AS income_category,
  COALESCE(ts.transaction_count, 0) AS transaction_count,
  CASE
    WHEN ts.total_income IS NULL OR ts.total_income = 0 THEN NULL
    ELSE ROUND((ts.total_income - ts.total_expense) * 1.0 / ts.total_income, 4)
  END AS savings_ratio,
  RANK() OVER (PARTITION BY hsd.region_name ORDER BY ls.max_loan_amount DESC) AS region_loan_rank
FROM account a
JOIN high_salary_districts hsd ON a.district_id = hsd.district_id
JOIN loan_stats ls ON a.account_id = ls.account
-- truncated
```
