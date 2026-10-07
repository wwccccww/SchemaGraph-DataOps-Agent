# 外部问数诊断

- 来源：bird
- 模型：deepseek-chat
- Prompt：text-to-sql-generic-v59
- 执行准确率：0.26
- 匹配：13
- SQL 错误：4
- 可执行率：0.92
- 方言错误率：0.0
- 上下文召回：1.0
- 引用表召回：0.9933333333333333
- 维度覆盖：1.0
- 实体覆盖：1.0
- 度量覆盖：0.972972972972973
- 结果不一致：33
- 电商规则命中用例：0
- 串库用例：0
- 这是注册库上的模型执行，不是 Gold-only，也不是官方 TPC-DS 分数。

## 未匹配

### bird_0002

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '']]
- 错误类别：None
- 脱敏错误：None
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：1.0
- 度量覆盖：1.0
- 种子表：['frpm', 'schools', 'satscores']
- 引用表：['frpm', 'satscores', 'schools']
- 投影：['Zip', 'City', 'CharterSchoolName', 'Charter Funding Type', 'Enrollment', 'PercentFRPM', 'FRPMCategory', 'YearOpened', 'CurrentStatus', 'SATTestTakers', 'TotalSATScore', 'PercentageAbove1500', 'SATRanking', 'EnrollmentRanking']
- 聚合：['rank']
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH base AS (SELECT frpm.CDSCode AS CDSCode, schools.Zip AS Zip, schools.City AS City, frpm."School Name" AS CharterSchoolName, frpm."Charter Funding Type" AS "Charter Funding Type", frpm."Enrollment (K-12)" AS Enrollment, frpm."Percent (%) Eligible FRPM (K-12)" AS PercentFRPM, CASE WHEN frpm."Percent (%) Eligible FRPM (K-12)" > 0.75 THEN 'Very High FRPM' WHEN frpm."Percent (%) Eligible FRPM (K-12)" > 0.50 THEN 'High FRPM' ELSE 'Low FRPM' END AS FRPMCategory, STRFTIME('%Y', schools.OpenDate) AS YearOpened, schools.StatusType AS CurrentStatus, satscores.NumTstTakr AS SATTestTakers, (satscores.AvgScrRead + satscores.AvgScrMath + satscores.AvgScrWrite) AS TotalSATScore, CASE WHEN satscores.NumTstTakr IS NULL THEN NULL ELSE CAST(satscores.NumGE1500 AS REAL) / satscores.NumTstTakr END AS PercentageAbove1500 FROM frpm JOIN schools ON frpm.CDSCode = schools.CDSCode LEFT JOIN satscores ON satscores.cds = schools.CDSCode AND satscores.rtype = 'S' WHERE frpm."District Name" = 'Fresno County Office of Education' AND frpm."Charter School (Y/N)" = 1 AND frpm."Enrollment (K-12)" > 0) SELECT Zip, City, CharterSchoolName, "Charter Funding Type", Enrollment, PercentFRPM, FRPMCategory, YearOpened, CurrentStatus, SATTestTakers, TotalSATScore, PercentageAbove1500, RANK() OVER (ORDER BY TotalSATScore DESC) AS SATRanking, RANK() OVER (ORDER BY Enrollment DESC) AS EnrollmentRanking FROM base ORDER BY CASE WHEN TotalSATScore IS NULL THEN 1 ELSE 0 END, TotalSATScore DESC, Enrollment DESC
```

### bird_0003

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：grouping_grain
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:aff8cdcbf2e97d8fbb2a73b752bd4de388fe26254bbf896a63bf32d2d03e097c;2:accepted:']]
- 错误类别：None
- 脱敏错误：None
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
WITH base AS (SELECT s.School AS SchoolName, s.County AS County, s.City AS City, s.MailStreet AS UnabbreviatedMailingAddress, s.Website AS Website, f."Enrollment (K-12)" AS Enrollment, f."FRPM Count (K-12)" AS FRPMCount, ROUND(f."Free Meal Count (K-12)" * 1.0 / f."Enrollment (K-12)" * 100, 2) AS FRPMPercentage, (COALESCE(sat.AvgScrRead, 0) + COALESCE(sat.AvgScrMath, 0) + COALESCE(sat.AvgScrWrite, 0)) AS TotalSATScore, sat.NumTstTakr, sat.NumGE1500, s.OpenDate AS OpenDate, s.StatusType AS SchoolStatus FROM frpm AS f JOIN schools AS s ON f.CDSCode = s.CDSCode LEFT JOIN satscores AS sat ON sat.cds = s.CDSCode AND sat.rtype = 'S' WHERE s.Charter = 0 AND f."Enrollment (K-12)" > 100) SELECT SchoolName, County, City, UnabbreviatedMailingAddress, Website, Enrollment, FRPMCount, FRPMPercentage, TotalSATScore, CASE WHEN NumTstTakr IS NULL THEN 'No SAT Data' WHEN TotalSATScore >= 1500 THEN 'High' WHEN TotalSATScore >= 1200 THEN 'Medium' ELSE 'Low' END AS PerformanceCategory, CASE WHEN NumTstTakr > 0 THEN ROUND(NumGE1500 * 100.0 / NumTstTakr, 2) END AS PercentHighScorers, CASE WHEN NumTstTakr IS NULL THEN 'No SAT Data' WHEN FRPMPercentage >= 75 AND (NumGE1500 * 100.0 / NumTstTakr) >= 30 THEN 'Performs well despite high FRPM' WHEN FRPMPercentage >= 75 AND (NumGE1500 * 100.0 / NumTstTakr) < 30 THEN 'Performs poorly given high FRPM' WHEN FRPMPercentage < 75 AND (NumGE1500 * 100.0 / NumTstTakr) >= 30 THEN 'Performs well given low FRPM' ELSE 'Performs poorly given low FRPM' END AS PerformanceClassification, OpenDate, SchoolStatus FROM base ORDER BY FRPMCount DESC LIMIT 1
```

### bird_0005

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:missing_entity:sha256:71fde2b71dc1807c35a3be351a2114ca1130b8e458a9bb1fccb32e3eed0d5f89;2:accepted:']]
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
SELECT schools.School AS SchoolName, schools.City AS City, CASE schools.Virtual WHEN 'F' THEN 'Fully Virtual' WHEN 'P' THEN 'Partially Virtual' WHEN 'N' THEN 'Not Virtual' ELSE 'Unknown' END AS VirtualStatus, CASE schools.Charter WHEN 1 THEN 'Charter School' ELSE 'Regular School' END AS SchoolType, satscores.AvgScrMath AS MathScore, satscores.AvgScrRead AS ReadingScore, satscores.AvgScrWrite AS WritingScore, (satscores.AvgScrRead + satscores.AvgScrMath + satscores.AvgScrWrite) AS TotalScore, RANK() OVER (ORDER BY satscores.AvgScrMath DESC) AS MathRank, RANK() OVER (ORDER BY (satscores.AvgScrRead + satscores.AvgScrMath + satscores.AvgScrWrite) DESC) AS TotalScoreRank, frpm."Enrollment (K-12)" AS Enrollment, CASE WHEN frpm."Percent (%) Eligible FRPM (K-12)" > 0.75 THEN 'Very High Poverty' WHEN frpm."Percent (%) Eligible FRPM (K-12)" > 0.50 THEN 'High Poverty' WHEN frpm."Percent (%) Eligible FRPM (K-12)" > 0.25 THEN 'Medium Poverty' ELSE 'Low Poverty' END AS PovertyLevel, ROUND(frpm."Percent (%) Eligible FRPM (K-12)" * 100, 1) || '%' AS FRPMPercentage FROM schools LEFT JOIN satscores ON satscores.cds = schools.CDSCode JOIN frpm ON frpm.CDSCode = schools.CDSCode WHERE schools.Virtual = 'F' AND satscores.AvgScrMath > 400 ORDER BY TotalScore DESC, Enrollment DESC
```

### bird_0006

- 数据库：california_schools
- 分类：sql_error
- 细分类：circuit_breaker
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:082ff66a6124d9ac0c79d920e698f996762d47cd542cd019cd65444c8c3e531b;2:no_progress:sha256:082ff66a6124d9ac0c79d920e698f996762d47cd542cd019cd65444c8c3e531b']]
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
- 聚合：['dense_rank']
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH base AS (
  SELECT
    s.School AS School,
    s.SOCType AS SchoolType,
    s.EdOpsName AS EducationalOption,
    sa.NumTstTakr AS TestTakers,
    (sa.AvgScrRead + sa.AvgScrMath + sa.AvgScrWrite) AS TotalAvgScore,
    sa.AvgScrRead AS ReadingScore,
    sa.AvgScrMath AS MathScore,
    sa.AvgScrWrite AS WritingScore,
    ROUND(sa.NumGE1500 * 100.0 / sa.NumTstTakr, 2) AS PercentHighScorers,
    f."Enrollment (K-12)" AS Enrollment,
    f."Percent (%) Eligible FRPM (K-12)" AS FreeReducedMealPercentage,
    s.County AS County
  FROM schools s
  JOIN satscores sa ON sa.cds = s.CDSCode
  LEFT JOIN frpm f ON f.CDSCode = s.CDSCode
  WHERE s.Magnet = 1
    AND sa.rtype = 'S'
    AND sa.NumTstTakr > 500
)
SELECT
  School,
  SchoolType,
  EducationalOption,
  TestTakers,
  TotalAvgScore,
  ReadingScore,
  MathScore,
  WritingScore,
  PercentHighScorers,
  Enrollment,
  FreeReducedMealPercentage,
  DENSE_RANK() OVER (ORDER BY TotalAvgScore DESC) AS StateRank,
  DENSE_RANK() OVER (PARTITION BY County ORDER BY TotalAvgScore DESC) AS CountyRank,
  CASE
    WHEN FreeReducedMealPercentage > 0.75 THEN 'High Poverty'
    WHEN FreeReducedMealPercentage > 0.50 THEN 'Moderate Poverty'
    WHEN FreeReducedMealPercentage > 0.25 THEN 'Low Poverty'
    ELSE 'Very Low Poverty'
  END AS PovertyLevel,
  CASE
    WHEN TotalAvgScore > 1800 THEN 'Excellent'
    WHEN TotalAvgScore > 1500 THEN 'Good'
    WHEN TotalAvgScore > 1200 THEN 'Average'
    ELSE 'Below Average'
  END AS PerformanceCategory
FROM base
ORDER BY TotalAvgScore DESC;
```

### bird_0008

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', 'ranked'], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:undefined_column:sha256:27d8cfa8dc43176cd3b7f5e8f1e182b3440b905f710d9508121cd1a510ae0674;2:accepted:']]
- 错误类别：None
- 脱敏错误：None
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
WITH base AS (SELECT frpm.CDSCode AS CDSCode, frpm."County Name" AS County, frpm."District Name" AS District, frpm."School Name" AS School, CASE WHEN frpm."Charter School (Y/N)" = 1 THEN 'Charter School' WHEN frpm."Charter School (Y/N)" = 0 THEN 'Non-Charter School' ELSE 'Unknown' END AS school_type, schools.GSserved AS grade_level, frpm."FRPM Count (K-12)" AS frpm_count, frpm."Enrollment (K-12)" AS enrollment, frpm."Percent (%) Eligible FRPM (K-12)" AS percent_eligible_frpm, satscores.NumTstTakr AS num_sat_takers, satscores.enroll12 AS sat_enroll12, satscores.AvgScrRead AS avg_reading, satscores.AvgScrMath AS avg_math, satscores.AvgScrWrite AS avg_writing, (satscores.AvgScrRead + satscores.AvgScrMath + satscores.AvgScrWrite) AS total_avg_score, satscores.NumGE1500 AS num_ge_1500 FROM frpm JOIN schools ON frpm.CDSCode = schools.CDSCode LEFT JOIN satscores ON satscores.cds = schools.CDSCode AND satscores.rtype = 'S' WHERE frpm."Enrollment (K-12)" > 0), ranked AS (SELECT base.CDSCode, base.County, base.District, base.School, base.school_type, base.grade_level, base.frpm_count, base.enrollment, base.percent_eligible_frpm, base.num_sat_takers, base.sat_enroll12, base.avg_reading, base.avg_math, base.avg_writing, base.total_avg_score, base.num_ge_1500, RANK() OVER (ORDER BY base.frpm_count DESC) AS frpm_rank FROM base) SELECT County, District, School, school_type, grade_level, frpm_count, enrollment, ROUND(percent_eligible_frpm * 100, 2) AS percent_eligible_frpm, num_sat_takers, ROUND(num_sat_takers * 100.0 / sat_enroll12, 2) AS percent_taking_sat, avg_reading, avg_math, avg_writing, total_avg_score, ROUND(num_ge_1500 * 100.0 / num_sat_takers, 2) AS percent_scoring_over_1500, frpm_rank FROM ranked WHERE frpm_rank <= 10 ORDER BY frpm_rank
```

### bird_0010

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', 'ranked'], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:8d3a71ee1e9b7ebe9005fcc7fe3e5cf56080ca418d59bbfb429e74734f663f13;2:accepted:']]
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
WITH ranked AS (SELECT s.cds, s.AvgScrRead, s.AvgScrMath, s.AvgScrWrite, s.NumTstTakr, s.NumGE1500, RANK() OVER (ORDER BY s.AvgScrRead DESC) AS ReadingRank FROM satscores AS s WHERE s.rtype = 'S' AND s.NumTstTakr > 10) SELECT sc.School AS SchoolName, sc.County AS County, sc.City AS City, sc.GSoffered AS GradeSpan, r.AvgScrRead AS ReadingScore, r.AvgScrMath AS MathScore, r.AvgScrWrite AS WritingScore, (r.AvgScrRead + r.AvgScrMath + r.AvgScrWrite) AS TotalSATScore, r.ReadingRank AS ReadingRank, f."FRPM Count (Ages 5-17)" AS FRPMCount, f."Percent (%) Eligible FRPM (Ages 5-17)" AS FRPMPercentage, f."Enrollment (Ages 5-17)" AS Enrollment, ROUND(r.NumGE1500 * 100.0 / r.NumTstTakr, 2) AS PercentScoring1500Plus, CASE WHEN sc.Charter = 1 THEN 'Charter School' ELSE 'Non-Charter School' END AS SchoolType, CASE WHEN f."Percent (%) Eligible FRPM (Ages 5-17)" > 0.75 THEN 'Very High Poverty' WHEN f."Percent (%) Eligible FRPM (Ages 5-17)" > 0.50 THEN 'High Poverty' WHEN f."Percent (%) Eligible FRPM (Ages 5-17)" > 0.25 THEN 'Moderate Poverty' ELSE 'Low Poverty' END AS PovertyLevel FROM ranked AS r JOIN schools AS sc ON sc.CDSCode = r.cds JOIN frpm AS f ON f.CDSCode = sc.CDSCode WHERE r.ReadingRank = 1 ORDER BY r.ReadingRank
```

### bird_0011

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:567dc338eecacc3a4614b9846ed98ad16accefa0584446eb336fc29f2741ea88;2:projection_mismatch:sha256:e39cce4f7725e3cd2ab3049734b1445d1ae5219aa0fb718ff971912511cf64e0;3:projection_mismatch:sha256:567dc338eecacc3a4614b9846ed98ad16accefa0584446eb336fc29f2741ea88;4:projection_mismatch:sha256:e39cce4f7725e3cd2ab3049734b1445d1ae5219aa0fb718ff971912511cf64e0;5:projection_mismatch:sha256:567dc338eecacc3a4614b9846ed98ad16accefa0584446eb336fc29f2741ea88']]
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
WITH base AS (
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
    AND (
      frpm."Percent (%) Eligible FRPM (K-12)" > 0.60
      OR (satscores.NumTstTakr > 0 AND CAST(satscores.NumGE1500 AS REAL) / satscores.NumTstTakr > 0.30)
    )
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
  RANK() OVER (PARTITION BY "County Name", FRPMCategory ORDER BY TotalSATScore DESC) AS CategorySATRank
FROM base
ORDER BY "County Name", CountyEnrollmentRank, CategorySATRank;
```

### bird_0012

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:undefined_column:sha256:9f77afb2190b019e9aefc66250903dd71919b1e6d6904ddb3cd0e659229b1f27;2:projection_mismatch:sha256:80c3c5257e4fbc14be348f33efca7d7f59d36659d4637a880a19fd78d34899f0;3:projection_mismatch:sha256:03ee002b014b5c67e0b02fb326030ecdf1bbde960c2414991771b9109f0d4807;4:projection_mismatch:sha256:80c3c5257e4fbc14be348f33efca7d7f59d36659d4637a880a19fd78d34899f0;5:projection_mismatch:sha256:03ee002b014b5c67e0b02fb326030ecdf1bbde960c2414991771b9109f0d4807']]
- 错误类别：projection_mismatch
- 脱敏错误：projection_mismatch: 口径：免费餐比例用 Free Meal Count (K-12) * 1.0 / Enrollment (K-12)；若无 FRPM 列再手算
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：1.0
- 度量覆盖：1.0
- 种子表：['schools', 'frpm', 'satscores']
- 引用表：['frpm', 'satscores', 'schools']
- 投影：['SchoolName', 'County', 'City', 'school_type', 'excellence_rate', 'eligible_free_rate', 'county_rank', 'avg_eligible_free_rate', 'free_meal_category']
- 聚合：['avg']
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH base AS (
  SELECT
    s.School AS SchoolName,
    s.County AS County,
    s.City AS City,
    CASE WHEN s.Charter = 1 THEN 'Charter School' ELSE 'Non-Charter School' END AS school_type,
    CAST(ss.NumGE1500 AS REAL) / ss.NumTstTakr AS excellence_rate,
    f."Free Meal Count (Ages 5-17)" * 1.0 / f."Enrollment (Ages 5-17)" AS eligible_free_rate
  FROM schools s
  JOIN satscores ss ON ss.cds = s.CDSCode
  JOIN frpm f ON f.CDSCode = s.CDSCode
  WHERE s.StatusType = 'Active'
    AND ss.rtype = 'S'
    AND ss.NumTstTakr > 0
    AND CAST(ss.NumGE1500 AS REAL) / ss.NumTstTakr > 0.3
    AND f."Enrollment (Ages 5-17)" > 0
),
ranked AS (
  SELECT
    b.SchoolName,
    b.County,
    b.City,
    b.school_type,
    b.excellence_rate,
    b.eligible_free_rate,
    RANK() OVER (PARTITION BY b.County ORDER BY b.eligible_free_rate DESC) AS county_rank
  FROM base b
)
SELECT
  r.SchoolName,
  r.County,
  r.City,
  r.school_type,
  r.excellence_rate,
  r.eligible_free_rate,
  r.county_rank,
  (SELECT AVG(eligible_free_rate) FROM base) AS avg_eligible_free_rate,
  CASE
    WHEN r.eligible_free_rate >= 0.75 THEN 'Very High Free Meal Rate'
    WHEN r.eligible_free_rate >= 0.50 THEN 'High Free Meal Rate'
    WHEN r.eligible_free_rate >= 0.25 THEN 'Medium Free Meal Rate'
    ELSE 'Low Free Meal Rate'
  END AS free_meal_category
FROM ranked r
WHERE r.county_rank = 1
ORDER BY r.eligible_free_rate DESC
LIMIT 1;
```

### bird_0013

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', 'ranked'], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:03ee002b014b5c67e0b02fb326030ecdf1bbde960c2414991771b9109f0d4807;2:projection_mismatch:sha256:d0c06eff1cb92a3e85834d3756a6f36868792b544f503a0263024d16a8b657a8;3:projection_mismatch:sha256:03ee002b014b5c67e0b02fb326030ecdf1bbde960c2414991771b9109f0d4807;4:projection_mismatch:sha256:d0c06eff1cb92a3e85834d3756a6f36868792b544f503a0263024d16a8b657a8;5:projection_mismatch:sha256:03ee002b014b5c67e0b02fb326030ecdf1bbde960c2414991771b9109f0d4807']]
- 错误类别：projection_mismatch
- 脱敏错误：projection_mismatch: 口径：免费餐比例用 Free Meal Count (K-12) * 1.0 / Enrollment (K-12)；若无 FRPM 列再手算
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
WITH school_sat AS (
  SELECT
    s.CDSCode,
    s.School AS "School Name",
    s.Phone AS "Contact Number",
    s.City AS "City",
    CASE s.Charter WHEN 1 THEN 'Yes' WHEN 0 THEN 'No' ELSE 'Unknown' END AS "Charter School",
    f."Percent (%) Eligible FRPM (K-12)" AS poverty_rate,
    ss.NumGE1500,
    ss.NumTstTakr,
    CAST(ss.NumGE1500 AS REAL) / ss.NumTstTakr AS excellence_rate
  FROM schools s
  JOIN satscores ss ON ss.cds = s.CDSCode AND ss.rtype = 'S'
  LEFT JOIN frpm f ON f.CDSCode = s.CDSCode
  WHERE ss.NumTstTakr > 0
),
ranked AS (
  SELECT
    *,
    RANK() OVER (ORDER BY excellence_rate DESC) AS sat_rank
  FROM school_sat
)
SELECT
  sat_rank AS "SAT Excellence Rank",
  "School Name",
  ROUND(excellence_rate, 4) AS "SAT Excellence Rate",
  NumGE1500 || '/' || NumTstTakr AS "High Scorers/Test Takers",
  "Contact Number",
  "City",
  "Charter School",
  ROUND(poverty_rate, 4) AS "Poverty Rate",
  CASE
    WHEN poverty_rate IS NULL THEN 'No FRPM Data'
    WHEN poverty_rate > 0.75 THEN 'Very High Poverty'
    WHEN poverty_rate > 0.50 THEN 'High Poverty'
    WHEN poverty_rate > 0.25 THEN 'Moderate Poverty'
    ELSE 'Low Poverty'
  END AS "Poverty Category"
FROM ranked
WHERE sat_rank <= 3
ORDER BY sat_rank;
```

### bird_0018

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'outer:ss."County Name"'], ['predicted_group_by', 'outer:county_name'], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '']]
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
- 分组：['county_name']
- 电商规则：[]
- 串库表：[]

```sql
WITH fresno_charter AS (SELECT f.CDSCode, f."County Name" AS county_name, f."Charter Funding Type" AS funding_type, f."Percent (%) Eligible FRPM (K-12)" AS frpm_pct, s.NumTstTakr, s.AvgScrRead, s.AvgScrMath, s.AvgScrWrite, s.NumGE1500, sc.OpenDate FROM frpm AS f JOIN schools AS sc ON f.CDSCode = sc.CDSCode LEFT JOIN satscores AS s ON s.cds = sc.CDSCode AND s.rtype = 'S' WHERE f."County Name" = 'Fresno' AND f."Charter Funding Type" = 'Directly funded' AND s.NumTstTakr <= 250) SELECT COUNT(DISTINCT CDSCode) AS TotalSchools, county_name AS "County Name", ROUND(AVG(NumTstTakr), 2) AS AvgTestTakers, ROUND(AVG(AvgScrRead + AvgScrMath + AvgScrWrite), 2) AS AvgTotalScore, ROUND(AVG(CAST(NumGE1500 AS REAL) * 100 / NumTstTakr), 2) AS AvgPercentScoring1500Plus, ROUND(AVG(frpm_pct) * 100, 2) AS AvgFRPMPercentage, ROUND(AVG((CAST(STRFTIME('%Y', '2026-10-01') AS INTEGER) - CAST(STRFTIME('%Y', OpenDate) AS INTEGER))), 2) AS AvgSchoolAgeInYears, SUM(CASE WHEN NumTstTakr <= 50 THEN 1 ELSE 0 END) AS SchoolsWithUnder50Testers, SUM(CASE WHEN NumTstTakr > 50 AND NumTstTakr <= 100 THEN 1 ELSE 0 END) AS SchoolsWith50To100Testers, SUM(CASE WHEN NumTstTakr > 100 AND NumTstTakr <= 250 THEN 1 ELSE 0 END) AS SchoolsWith100To250Testers FROM fresno_charter GROUP BY county_name
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
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:undefined_column:sha256:81c15eb11415dde2982b0230cea8f44def995a868c4b10d034f412349df55a7d;2:projection_mismatch:sha256:7eaf654117db5b6f0d3c7836dd96c93405f2b0654f1b98eb17682aab130a8929;3:projection_mismatch:sha256:4a2991da088bb0323e5d790937179f1071c68973f4f2d8b076e712cd8c8a249a;4:projection_mismatch:sha256:257c017cc4b8d9cc6ce406f8b136ca1628006da7502ba486ffb046b85fa02bf6;5:accepted:']]
- 错误类别：None
- 脱敏错误：None
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
WITH SchoolInfo AS (SELECT s.CDSCode, s.School, s.District, s.Charter AS CharterFlag, f."Enrollment (K-12)" AS Enrollment, f."Free Meal Count (K-12)" AS FreeMealCount, f."Percent (%) Eligible FRPM (K-12)" AS FRPMPct FROM schools AS s JOIN frpm AS f ON f.CDSCode = s.CDSCode WHERE s.County = 'Amador' AND s.StatusType = 'Active' AND f."Low Grade" = '9' AND f."High Grade" = '12'), SATData AS (SELECT sc.cds, sc.NumTstTakr, sc.NumGE1500, (sc.AvgScrRead + sc.AvgScrMath + sc.AvgScrWrite) AS TotalScore FROM satscores AS sc WHERE sc.rtype = 'S'), Joined AS (SELECT si.CDSCode, si.School, si.District, si.CharterFlag, si.Enrollment, si.FRPMPct, sd.NumTstTakr, sd.NumGE1500, sd.TotalScore, CASE WHEN si.FRPMPct IS NULL THEN NULL WHEN si.FRPMPct > 0.75 THEN 'High Poverty' ELSE 'Not High Poverty' END AS PovertyLevel, ROW_NUMBER() OVER (ORDER BY si.Enrollment DESC) AS EnrollmentRank FROM SchoolInfo AS si LEFT JOIN SATData AS sd ON sd.cds = si.CDSCode) SELECT COUNT(*) AS TotalSchools, ROUND(AVG(Enrollment), 2) AS AvgEnrollment, SUM(CASE WHEN CharterFlag = 1 THEN 1 ELSE 0 END) AS CharterSchools, SUM(CASE WHEN CharterFlag = 0 THEN 1 ELSE 0 END) AS NonCharterSchools, ROUND(AVG(FRPMPct) * 100, 2) AS AvgFRPMPercentage, (SELECT COUNT(DISTINCT District) FROM SchoolInfo) AS DistrictCount, ROUND(AVG(TotalScore), 2) AS AvgSATScore, ROUND(MAX(CASE WHEN NumTstTakr > 0 THEN NumGE1500 * 100.0 / NumTstTakr END), 2) AS MaxPercentAbove1500, (SELECT School FROM Joined WHERE EnrollmentRank = 1) AS LargestSchool, SUM(CASE WHEN PovertyLevel = 'High Poverty' THEN 1 ELSE 0 END) AS HighPovertySchools FROM Joined
```

### bird_0021

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'CategoryBreakdown:FreeMealCategory'], ['predicted_group_by', 'CategoryBreakdown:FreeMealCategory'], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=3;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:3e820826c67db8f8e44ae1f47ba0a46f692139f6034741e513da01819098654d;2:accepted:']]
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
- 聚合：['count', 'avg', 'sum', 'group_concat']
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH SchoolMealStats AS (SELECT f.CDSCode, f."Free Meal Count (K-12)" AS FreeMealCount, f."FRPM Count (K-12)" AS FRPMCount, f."Enrollment (K-12)" AS Enrollment, f."Free Meal Count (K-12)" * 1.0 / f."Enrollment (K-12)" AS FreePercentage, f."Percent (%) Eligible FRPM (K-12)" AS FRPMPercentage, sc.Charter AS CharterFlag, s.AvgScrRead + s.AvgScrMath + s.AvgScrWrite AS TotalSATScore, CASE WHEN f."Free Meal Count (K-12)" > 500 THEN 'Very High Free Meal' WHEN f."Free Meal Count (K-12)" > 300 THEN 'High Free Meal' WHEN f."Free Meal Count (K-12)" > 100 THEN 'Moderate Free Meal' ELSE 'Low Free Meal' END AS FreeMealCategory FROM frpm AS f JOIN schools AS sc ON f.CDSCode = sc.CDSCode LEFT JOIN satscores AS s ON s.cds = sc.CDSCode AND s.rtype = 'S' WHERE sc.County = 'Los Angeles' AND f."Free Meal Count (K-12)" > 500 AND f."FRPM Count (K-12)" < 700 AND f."Enrollment (K-12)" > 0), CategoryBreakdown AS (SELECT FreeMealCategory, COUNT(*) AS CategoryCount FROM SchoolMealStats GROUP BY FreeMealCategory) SELECT COUNT(*) AS TotalSchools, ROUND(AVG(FreeMealCount), 2) AS AvgFreeMeals, ROUND(AVG(FRPMCount), 2) AS AvgTotalFRPM, ROUND(AVG(FreePercentage), 4) AS AvgFreePercentage, ROUND(AVG(FRPMPercentage), 2) AS AvgFRPMPercentage, SUM(CASE WHEN CharterFlag = 1 THEN 1 ELSE 0 END) AS CharterSchoolCount, SUM(CASE WHEN CharterFlag = 0 THEN 1 ELSE 0 END) AS NonCharterSchoolCount, ROUND(AVG(TotalSATScore), 2) AS AvgSATScore, (SELECT COUNT(*) FROM SchoolMealStats WHERE TotalSATScore IS NULL) AS SchoolsWithoutSATData, (SELECT GROUP_CONCAT(FreeMealCategory || ': ' || CategoryCount, '; ') FROM CategoryBreakdown) AS FreeMealCategoryBreakdown FROM SchoolMealStats
```

### bird_0032

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', 'ranked'], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:undefined_column:sha256:27d8cfa8dc43176cd3b7f5e8f1e182b3440b905f710d9508121cd1a510ae0674;2:accepted:']]
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
WITH base AS (SELECT frpm.CDSCode AS CDSCode, frpm."School Name" AS School, frpm."County Name" AS County, frpm."District Name" AS District, schools.SOCType AS SOCType, frpm."Enrollment (K-12)" AS Enrollment, frpm."FRPM Count (K-12)" AS FRPMCount, frpm."Free Meal Count (K-12)" AS FreeMealCount, frpm."Free Meal Count (K-12)" * 1.0 / NULLIF(frpm."Enrollment (K-12)", 0) AS FreeRate, frpm."FRPM Count (K-12)" * 1.0 / NULLIF(frpm."Enrollment (K-12)", 0) AS FRPMRate, satscores.NumTstTakr AS SATTestTakers, satscores.AvgScrRead AS AvgReading, satscores.AvgScrMath AS AvgMath, satscores.AvgScrWrite AS AvgWriting, (satscores.AvgScrRead + satscores.AvgScrMath + satscores.AvgScrWrite) AS TotalSATScore, satscores.NumGE1500 AS NumGE1500 FROM frpm JOIN schools ON frpm.CDSCode = schools.CDSCode LEFT JOIN satscores ON satscores.cds = schools.CDSCode AND satscores.rtype = 'S' WHERE schools.SOC = '66'), ranked AS (SELECT base.CDSCode, base.School, base.County, base.District, base.SOCType, base.Enrollment, base.FRPMCount, base.FreeMealCount, base.FreeRate, base.FRPMRate, base.SATTestTakers, base.AvgReading, base.AvgMath, base.AvgWriting, base.TotalSATScore, base.NumGE1500, RANK() OVER (ORDER BY base.FRPMCount DESC) AS FRPMRank FROM base) SELECT FRPMRank, School, County, District, SOCType, Enrollment, FRPMCount, ROUND(FreeRate * 100, 2) || '%' AS EligibilityRate, CASE WHEN FRPMRate > 0.75 THEN 'Very High FRPM' WHEN FRPMRate > 0.50 THEN 'High FRPM' WHEN FRPMRate > 0.25 THEN 'Moderate FRPM' ELSE 'Low FRPM' END AS EligibilityCategory, SATTestTakers, AvgReading, AvgMath, AvgWriting, TotalSATScore, CASE WHEN SATTestTakers IS NULL OR SATTestTakers = 0 THEN NULL ELSE ROUND(NumGE1500 * 1.0 / SATTestTakers * 100, 2) || '%' END AS HighSATScorerRate, CASE WHEN Enrollment IS NULL OR Enrollment = 0 THEN NULL ELSE ROUND(SATTestTakers * 1.0 / Enrollment * 100, 2) || '%' END AS SATParticipationRate FROM ranked WHERE FRPMRank <= 5 ORDER BY FRPMRank
```

### bird_0045

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'DistrictAverages:s.District'], ['predicted_group_by', 'DistrictAverages:s.District'], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=4;predicted=3'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '']]
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
WITH SchoolStats AS (SELECT s.School AS School, ss.AvgScrWrite AS AvgScrWrite, ss.AvgScrRead AS AvgScrRead, ss.AvgScrMath AS AvgScrMath, (ss.AvgScrRead + ss.AvgScrMath + ss.AvgScrWrite) AS TotalSATScore, ss.NumTstTakr AS NumTstTakr, f."Enrollment (K-12)" AS "Enrollment (K-12)", ROUND(f."Percent (%) Eligible FRPM (K-12)" * 100, 2) AS FRPMPercentage, s.District AS District FROM schools AS s JOIN satscores AS ss ON ss.cds = s.CDSCode JOIN frpm AS f ON f.CDSCode = s.CDSCode WHERE s.AdmFName1 = 'Ricci' AND s.AdmLName1 = 'Ulrich' AND f."Enrollment (K-12)" > 0), DistrictAverages AS (SELECT s.District AS District, AVG(ss.AvgScrWrite) AS DistrictAvgWriteScore FROM schools AS s JOIN satscores AS ss ON ss.cds = s.CDSCode GROUP BY s.District) SELECT st.School AS School, st.AvgScrWrite AS AvgScrWrite, st.AvgScrRead AS AvgScrRead, st.AvgScrMath AS AvgScrMath, st.TotalSATScore AS TotalSATScore, st.NumTstTakr AS NumTstTakr, st."Enrollment (K-12)" AS "Enrollment (K-12)", st.FRPMPercentage AS FRPMPercentage, RANK() OVER (ORDER BY st.AvgScrWrite DESC) AS WriteScoreRank, RANK() OVER (ORDER BY st.TotalSATScore DESC) AS TotalScoreRank, ROUND(da.DistrictAvgWriteScore, 2) AS DistrictAvgWriteScore, CASE WHEN st.AvgScrWrite > da.DistrictAvgWriteScore THEN 'Above District Average' WHEN st.AvgScrWrite = da.DistrictAvgWriteScore THEN 'Equal to District Average' ELSE 'Below District Average' END AS ComparisonToDistrictAvg, ROUND(st.AvgScrWrite - da.DistrictAvgWriteScore, 2) AS DifferenceFromDistrictAvg, ROUND(st.NumTstTakr * 100.0 / st."Enrollment (K-12)", 2) AS PercentageTakingSAT FROM SchoolStats AS st JOIN DistrictAverages AS da ON da.District = st.District ORDER BY st.School
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
    SUM(CASE WHEN s.Charter = 1 THEN 1 ELSE 0 END) AS charter_schools,
    SUM(CASE WHEN f."Percent (%) Eligible FRPM (K-12)" > 0.5 THEN 1 ELSE 0 END) AS high_frpm_schools,
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
    SUM(CASE WHEN s.Charter = 1 THEN 1 ELSE 0 END) AS charter_schools,
    SUM(CASE WHEN f."Percent (%) Eligible FRPM (K-12)" > 0.5 THEN 1 ELSE 0 END) AS high_frpm_schools,
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
SELECT 'Total Enrollment Ratio', ROUND(c.total_enrollment * 1.0 / NULLIF(h.total_enrollment, 0), 4) FROM colusa c, humboldt h
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
SELECT schools.School AS SchoolName, schools.Website AS Website, schools.CharterNum AS CharterNumber, schools.FundingType AS FundingType, frpm."Enrollment (K-12)" AS TotalEnrollment, frpm."FRPM Count (K-12)" AS FRPMCount, ROUND(frpm."Percent (%) Eligible FRPM (K-12)" * 100, 2) || '%' AS FRPMPercentage, CASE WHEN frpm."Percent (%) Eligible FRPM (K-12)" > 0.75 THEN 'Very High Poverty' WHEN frpm."Percent (%) Eligible FRPM (K-12)" > 0.50 THEN 'High Poverty' WHEN frpm."Percent (%) Eligible FRPM (K-12)" > 0.25 THEN 'Moderate Poverty' ELSE 'Low Poverty' END AS PovertyLevel, RANK() OVER (ORDER BY frpm."Enrollment (K-12)" DESC) AS EnrollmentRank, satscores.NumTstTakr AS SATTestTakers, satscores.AvgScrRead AS AvgReadingScore, satscores.AvgScrMath AS AvgMathScore, satscores.AvgScrWrite AS AvgWritingScore, satscores.NumGE1500 AS StudentsOver1500, CASE WHEN satscores.NumTstTakr IS NULL OR satscores.NumTstTakr = 0 THEN 'No SAT Data' WHEN satscores.NumGE1500 IS NULL THEN 'No SAT Data' ELSE ROUND(satscores.NumGE1500 * 100.0 / satscores.NumTstTakr, 2) || '%' END AS PercentOver1500 FROM schools JOIN frpm ON frpm.CDSCode = schools.CDSCode LEFT JOIN satscores ON satscores.cds = schools.CDSCode AND satscores.rtype = 'S' WHERE schools.Virtual = 'P' AND schools.Charter = 1 AND schools.County = 'San Joaquin' ORDER BY EnrollmentRank
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
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'CountyStats:County'], ['predicted_group_by', ''], ['aggregation_only_in_cte', 'countystats'], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=3;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:cartesian_product:sha256:8e47d25106709f6d98e82e6194330456cda682737508a6fc276c53df5390fae7;2:join_not_on_graph:sha256:ec0d30d719f6b6e5dee91402f291378925300336e30d200742b855880b917cbf;3:kept_candidate:join_not_on_graph']]
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
WITH base AS (SELECT frpm.CDSCode AS CDSCode, frpm."School Name" AS School, frpm."District Name" AS District, frpm."County Name" AS County, frpm."Enrollment (K-12)" AS Enrollment, frpm."Free Meal Count (K-12)" AS FreeMealCount, frpm."Free Meal Count (K-12)" * 1.0 / frpm."Enrollment (K-12)" * 100 AS FreePercentage FROM frpm JOIN schools ON frpm.CDSCode = schools.CDSCode WHERE schools.Charter = 0 AND frpm."County Name" = 'Los Angeles' AND frpm."Enrollment (K-12)" > 0), lowfree AS (SELECT * FROM base WHERE FreePercentage < 0.18), countystats AS (SELECT COUNT(*) AS TotalSchools, SUM(CASE WHEN FreePercentage < 0.18 THEN 1 ELSE 0 END) AS LowFreeSchools, AVG(FreePercentage) AS CountyAvgFreePercent FROM base) SELECT lf.CDSCode AS CDSCode, lf.School AS School, lf.District AS District, lf.County AS County, lf.Enrollment AS Enrollment, lf.FreeMealCount AS FreeMealCount, ROUND(lf.FreePercentage, 2) AS FreePercentage, CASE WHEN lf.FreePercentage < 0.05 THEN 'Very Low' WHEN lf.FreePercentage < 0.10 THEN 'Low' WHEN lf.FreePercentage < 0.18 THEN 'Medium' ELSE 'High' END AS FreeCategory, ROW_NUMBER() OVER (ORDER BY lf.FreePercentage ASC) AS CountyRank, cs.TotalSchools AS TotalSchools, cs.LowFreeSchools AS LowFreeSchools, ROUND(cs.CountyAvgFreePercent, 2) AS CountyAvgFreePercent, ROUND(cs.LowFreeSchools * 100.0 / cs.TotalSchools, 2) || '%' AS PctLowFreeInCounty, cs.LowFreeSchools AS LATotalLowFree FROM lowfree AS lf CROSS JOIN countystats AS cs ORDER BY lf.FreePercentage ASC
```

### bird_0066

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：grouping_grain
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'CountyStats:County'], ['predicted_group_by', ''], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=3;predicted=3'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:80bef9fc7bcf13f9e589ff2bdc54bd2fdb5ad0f165e331868f762298b6497a9c;2:join_not_on_graph:sha256:ec0d30d719f6b6e5dee91402f291378925300336e30d200742b855880b917cbf;3:projection_mismatch:sha256:5628cadba8d47632f24fb21dd090770c707dabd4082c287d888931a619135cec;4:kept_candidate:projection_mismatch']]
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
WITH base AS (SELECT s.School AS School, s.OpenDate AS OpenDate, STRFTIME('%Y', s.OpenDate) AS OpenYear, f."Enrollment (K-12)" AS Enrollment, f."FRPM Count (K-12)" AS FRPMCount, f."Percent (%) Eligible FRPM (K-12)" AS FRPMPercent, CASE WHEN f."Charter School (Y/N)" = 1 THEN 'Charter School' ELSE 'Non-Charter School' END AS SchoolType, sa.AvgScrRead AS AvgScrRead, sa.AvgScrMath AS AvgScrMath, sa.AvgScrWrite AS AvgScrWrite, (sa.AvgScrRead + sa.AvgScrMath + sa.AvgScrWrite) AS TotalSATScore FROM frpm AS f JOIN schools AS s ON f.CDSCode = s.CDSCode LEFT JOIN satscores AS sa ON sa.cds = s.CDSCode AND sa.rtype = 'S' WHERE s.FundingType = 'Directly funded' AND s.County = 'Stanislaus' AND NOT s.OpenDate IS NULL AND STRFTIME('%Y', s.OpenDate) BETWEEN '2000' AND '2005' AND f."Enrollment (K-12)" > 0), countystats AS (SELECT COUNT(DISTINCT CDSCode) AS CountyTotalSchools, AVG("Enrollment (K-12)") AS CountyAvgEnrollment, AVG("Percent (%) Eligible FRPM (K-12)") AS CountyAvgFRPMPercent FROM frpm WHERE "County Name" = 'Stanislaus' AND "Enrollment (K-12)" > 0) SELECT b.School AS School, b.OpenDate AS OpenDate, b.OpenYear AS OpenYear, b.Enrollment AS Enrollment, b.FRPMCount AS FRPMCount, b.FRPMPercent AS FRPMPercent, b.SchoolType AS SchoolType, b.AvgScrRead AS AvgScrRead, b.AvgScrMath AS AvgScrMath, b.AvgScrWrite AS AvgScrWrite, b.TotalSATScore AS TotalSATScore, c.CountyTotalSchools AS CountyTotalSchools, c.CountyAvgEnrollment AS CountyAvgEnrollment, c.CountyAvgFRPMPercent AS CountyAvgFRPMPercent, CASE WHEN b.FRPMPercent > c.CountyAvgFRPMPercent THEN 'Above County Average' WHEN b.FRPMPercent < c.CountyAvgFRPMPercent THEN 'Below County Average' ELSE 'At County Average' END AS FRPMStatus, RANK() OVER (ORDER BY b.FRPMPercent DESC) AS FRPMRank, RANK() OVER (ORDER BY b.TotalSATScore DESC) AS SATScoreRank FROM base AS b JOIN countystats AS c ON 1 = 1 ORDER BY FRPMRank, SATScoreRank
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
- 聚合：['rank']
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
SELECT
  schools.NCESDist AS NCESDist,
  schools.School AS School,
  CASE schools.Charter WHEN 1 THEN 'Charter' WHEN 0 THEN 'Non-Charter' ELSE 'Unknown' END AS SchoolType,
  schools.StatusType AS CurrentStatus,
  date(schools.OpenDate) AS OpeningDate,
  frpm."Enrollment (K-12)" AS Enrollment,
  CASE
    WHEN frpm."Percent (%) Eligible FRPM (K-12)" > 0.75 THEN 'Very High Poverty'
    WHEN frpm."Percent (%) Eligible FRPM (K-12)" > 0.50 THEN 'High Poverty'
    WHEN frpm."Percent (%) Eligible FRPM (K-12)" > 0.25 THEN 'Moderate Poverty'
    ELSE 'Low Poverty'
  END AS PovertyLevel,
  satscores.AvgScrRead AS AvgReadingScore,
  satscores.AvgScrMath AS AvgMathScore,
  satscores.AvgScrWrite AS AvgWritingScore,
  ROUND((satscores.AvgScrRead + satscores.AvgScrMath + satscores.AvgScrWrite) / 3.0, 2) AS AvgTotalScore,
  RANK() OVER (ORDER BY frpm."Enrollment (K-12)" DESC) AS EnrollmentRank
FROM schools
JOIN frpm ON frpm.CDSCode = schools.CDSCode
LEFT JOIN satscores ON satscores.cds = schools.CDSCode AND satscores.rtype = 'S'
WHERE schools.DOCType = 'State Special Schools'
  AND schools.SOC LIKE '3%'
ORDER BY frpm."Enrollment (K-12)" DESC;
```

### bird_0077

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:87747a7ff493b4eb19ed2072bfffdf471909ebd2573220dcb4cd0639ef82d64a;2:projection_mismatch:sha256:41407be8daa3accacb43e45adc805da0b1aaf0da7c693e95de19bdc27a381ec8;3:projection_mismatch:sha256:b6bac20361ad371766567d13e735895a1c02a26ed3c354da5fc0007098a4367b;4:projection_mismatch:sha256:b5e3ccee9d8467fd9aa51a9113d2ec03f604bed074012174b0f6176f18477b21;5:projection_mismatch:sha256:b6bac20361ad371766567d13e735895a1c02a26ed3c354da5fc0007098a4367b']]
- 错误类别：projection_mismatch
- 脱敏错误：projection_mismatch: FRPM 与 Enrollment 用 Ages 5-17 列；Percent 用 FRPM Count/Enrollment×100；projection_mismatch: 口径：FRPM 比例用 frpm `Percent (%) Eligible FRPM (K-12)` * 100 AS FRPMPercentage，不要仅用 Free Meal Count/Enrollment 重算；projection_mismatch: 县级过滤优先用 frpm.`County Name`（或 schools.County 与问句县名一致），不要混用错误县列导致漏行。
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
  schools.School AS "School",
  schools.City AS "City",
  ROUND(frpm."Percent (%) Eligible FRPM (K-12)" * 100, 2) AS "Percent (%) Eligible FRPM (Ages 5-17)",
  CASE
    WHEN frpm."Percent (%) Eligible FRPM (K-12)" > 0.75 THEN 'High Poverty'
    WHEN frpm."Percent (%) Eligible FRPM (K-12)" > 0.50 THEN 'Medium Poverty'
    ELSE 'Low Poverty'
  END AS "Poverty_Level",
  CASE schools.Charter WHEN 1 THEN 'Yes' WHEN 0 THEN 'No' ELSE 'Unknown' END AS "Is_Charter",
  satscores.NumTstTakr AS "Number of SAT Test Takers",
  satscores.AvgScrRead AS "Avg Reading Score",
  satscores.AvgScrMath AS "Avg Math Score",
  satscores.AvgScrWrite AS "Avg Writing Score",
  (satscores.AvgScrRead + satscores.AvgScrMath + satscores.AvgScrWrite) AS "Total SAT Score",
  RANK() OVER (ORDER BY frpm."Percent (%) Eligible FRPM (K-12)" DESC) AS "SAT Ranking",
  frpm."FRPM Count (Ages 5-17)" AS "FRPM Count",
  frpm."Enrollment (Ages 5-17)" AS "Enrollment"
FROM schools
JOIN frpm ON frpm.CDSCode = schools.CDSCode
LEFT JOIN satscores ON satscores.cds = schools.CDSCode AND satscores.rtype = 'S'
WHERE schools.County = 'Los Angeles'
  AND schools.GSserved = 'K-9'
  AND frpm."Enrollment (K-12)" > 0
ORDER BY frpm."Percent (%) Eligible FRPM (K-12)" DESC;
```

### bird_0078

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：join_semantics
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'outer:sbs.GSserved、sbs.school_count | SchoolsByGradeSpan:s.GSserved'], ['predicted_group_by', 'GradeSpanCounts:"GSserved"'], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=3;predicted=3'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '']]
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
WITH "AdelantoSchools" AS (SELECT s."CDSCode" AS "CDSCode", s."GSserved" AS "GSserved", s."StatusType" AS "StatusType", f."Enrollment (K-12)" AS "Enrollment", f."Percent (%) Eligible FRPM (K-12)" AS "FRPMPct", sa."AvgScrRead" AS "AvgScrRead", sa."AvgScrMath" AS "AvgScrMath", sa."AvgScrWrite" AS "AvgScrWrite" FROM schools AS s JOIN frpm AS f ON f."CDSCode" = s."CDSCode" LEFT JOIN satscores AS sa ON sa.cds = s."CDSCode" AND sa.rtype = 'S' WHERE s."City" = 'Adelanto' AND s."StatusType" = 'Active'), "GradeSpanCounts" AS (SELECT "GSserved", COUNT(*) AS "cnt", RANK() OVER (ORDER BY COUNT(*) DESC) AS "grade_span_rank" FROM "AdelantoSchools" GROUP BY "GSserved"), "MostCommon" AS (SELECT "GSserved" AS "most_common_grade_span" FROM "GradeSpanCounts" WHERE "grade_span_rank" = 1) SELECT m."most_common_grade_span" AS "most_common_grade_span", COUNT(a."CDSCode") AS "school_count", SUM(CASE WHEN a."StatusType" = 'Active' THEN 1 ELSE 0 END) AS "active_schools", ROUND(AVG(a."Enrollment"), 2) AS "avg_enrollment", SUM(a."Enrollment") AS "total_enrollment", ROUND(AVG(a."FRPMPct"), 2) AS "avg_frpm_percentage", SUM(CASE WHEN a."FRPMPct" > 0.75 THEN 1 ELSE 0 END) AS "high_poverty_schools", SUM(CASE WHEN a."FRPMPct" > 0.50 AND a."FRPMPct" <= 0.75 THEN 1 ELSE 0 END) AS "medium_poverty_schools", SUM(CASE WHEN a."FRPMPct" <= 0.50 THEN 1 ELSE 0 END) AS "low_poverty_schools", ROUND(AVG(a."AvgScrRead"), 2) AS "avg_reading_score", ROUND(AVG(a."AvgScrMath"), 2) AS "avg_math_score", ROUND(AVG(a."AvgScrWrite"), 2) AS "avg_writing_score" FROM "AdelantoSchools" AS a JOIN "MostCommon" AS m ON a."GSserved" = m."most_common_grade_span"
```

### bird_0079

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'CountyStats:County'], ['predicted_group_by', 'county_stats:County'], ['aggregation_only_in_cte', 'county_stats,ranked'], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=3'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:c163fd8782d2d79bc8a76e4c6044dbb35fc735881770d2fb8e94aceac5438416;2:projection_mismatch:sha256:3e820826c67db8f8e44ae1f47ba0a46f692139f6034741e513da01819098654d;3:accepted:']]
- 错误类别：None
- 脱敏错误：None
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
WITH virtual_schools AS (SELECT s.CDSCode, s.County, s.School, s.Charter AS charter_flag, f."Enrollment (K-12)" AS enrollment, f."Free Meal Count (K-12)" AS free_meal, (COALESCE(ss.AvgScrRead, 0) + COALESCE(ss.AvgScrMath, 0) + COALESCE(ss.AvgScrWrite, 0)) AS sat_total FROM schools AS s LEFT JOIN frpm AS f ON f.CDSCode = s.CDSCode LEFT JOIN satscores AS ss ON ss.cds = s.CDSCode AND ss.rtype = 'S' WHERE s.Virtual = 'F' AND s.County IN ('San Diego', 'Santa Barbara')), county_stats AS (SELECT County, COUNT(*) AS amount, SUM(CASE WHEN charter_flag = 1 THEN 1 ELSE 0 END) AS CharterSchools, SUM(CASE WHEN charter_flag = 0 THEN 1 ELSE 0 END) AS RegularSchools, AVG(enrollment) AS AverageEnrollment, MAX(enrollment) AS HighestEnrollment, MIN(enrollment) AS LowestEnrollment, AVG(CASE WHEN enrollment > 0 THEN free_meal * 1.0 / enrollment * 100 END) AS AvgFreeReducedMealPercentage, AVG(CASE WHEN sat_total > 0 THEN sat_total END) AS AverageSATScore FROM virtual_schools GROUP BY County), ranked AS (SELECT *, RANK() OVER (ORDER BY amount DESC) AS CountyRank FROM county_stats), largest AS (SELECT County, School AS LargestVirtualSchool, ROW_NUMBER() OVER (PARTITION BY County ORDER BY enrollment DESC) AS rn FROM virtual_schools) SELECT r.County AS County, r.amount AS amount, r.CharterSchools AS CharterSchools, r.RegularSchools AS RegularSchools, r.AverageEnrollment AS AverageEnrollment, r.HighestEnrollment AS HighestEnrollment, r.LowestEnrollment AS LowestEnrollment, ROUND(r.AvgFreeReducedMealPercentage, 2) || '%' AS AvgFreeReducedMealPercentage, r.AverageSATScore AS AverageSATScore, l.LargestVirtualSchool AS LargestVirtualSchool FROM ranked AS r JOIN largest AS l ON l.County = r.County AND l.rn = 1 WHERE r.CountyRank = 1
```

### bird_0092

- 数据库：financial
- 分类：sql_error
- 细分类：circuit_breaker
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'DistrictStats:d.district_id、d.A2、d.A3、d.A11 | AccountActivity:a.district_id'], ['predicted_group_by', 'district_stats:d.district_id、d.A3、d.A11'], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=5;predicted=7'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:undefined_column:sha256:16d8950b68a6fd0d20250980a3090f85a438b9ff4fe5353c714b6900e0e6b7fb;2:projection_mismatch:sha256:19ce85cb5b40c1c5e30f74f1edb04acce262f78ac9f833ea57c6024a0413789f;3:no_progress:sha256:19ce85cb5b40c1c5e30f74f1edb04acce262f78ac9f833ea57c6024a0413789f']]
- 错误类别：no_progress
- 脱敏错误：修复没有改变症状，已标记 no_progress 并熔断
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
WITH female_clients AS (
  SELECT c.client_id, c.birth_date, c.district_id
  FROM client c
  WHERE c.gender = 'F'
),
district_stats AS (
  SELECT d.district_id, d.A3 AS region, d.A11 AS avg_salary,
         COUNT(DISTINCT fc.client_id) AS female_clients
  FROM district d
  JOIN female_clients fc ON fc.district_id = d.district_id
  GROUP BY d.district_id, d.A3, d.A11
  HAVING d.A11 BETWEEN 6000 AND 10000 AND COUNT(DISTINCT fc.client_id) >= 5
),
ranked AS (
  SELECT district_id, region, avg_salary, female_clients,
         RANK() OVER (PARTITION BY region ORDER BY avg_salary DESC) AS salary_rank_in_region
  FROM district_stats
),
qualified AS (
  SELECT district_id, region, avg_salary, female_clients
  FROM ranked
  WHERE salary_rank_in_region <= 3
),
account_activity AS (
  SELECT a.account_id, a.district_id, fc.client_id, fc.birth_date
  FROM account a
  JOIN disp dp ON dp.account_id = a.account_id AND dp.type = 'OWNER'
  JOIN female_clients fc ON fc.client_id = dp.client_id
  JOIN qualified q ON q.district_id = a.district_id
),
loan_stats AS (
  SELECT aa.client_id, aa.account_id, l.loan_id, l.amount, l.status
  FROM account_activity aa
  JOIN loan l ON l.account_id = aa.account_id
)
SELECT
  COUNT(DISTINCT q.district_id) AS district_count,
  COUNT(DISTINCT aa.client_id) AS total_female_clients,
  AVG(q.avg_salary) AS average_female_salary,
  AVG(2026 - CAST(STRFTIME('%Y', aa.birth_date) AS INTEGER)) AS average_female_age,
  COUNT(DISTINCT aa.account_id) AS total_female_accounts,
  COUNT(ls.loan_id) AS total_female_loans,
  AVG(ls.amount) AS average_female_loan_amount,
  SUM(CASE WHEN ls.status = 'A' THEN 1 ELSE 0 END) AS active_female_loans,
  SUM(CASE WHEN ls.status = 'B' THEN 1 ELSE 0 END) AS completed_female_loans,
  SUM(CASE WHEN ls.status = 'C' THEN 1 ELSE 0 END) AS defaulted_female_loans,
  GROUP_CONCAT(DISTINCT q.region) AS regions_represented
FROM qualified q
JOIN account_activity aa ON aa.district_id = q.district_id
LEFT JOIN loan_stats ls ON ls.client_id
-- truncated
```

### bird_0096

- 数据库：financial
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'outer:ci.gender、ci.age_group、ci.region | CustomerWeeklyStatements:T2.client_id、T1.account_id、T1.district_id、T1.date | LoanAndTransactionData:cws.client_id'], ['predicted_group_by', 'outer:gender、age_group、region'], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=7;predicted=10'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '']]
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
- 分组：['gender', 'age_group', 'region']
- 电商规则：[]
- 串库表：[]

```sql
WITH CustomerWeeklyStatements AS (SELECT c.client_id, c.gender, c.birth_date, c.district_id, a.account_id FROM account AS a JOIN disp AS d ON d.account_id = a.account_id AND d.type = 'OWNER' JOIN client AS c ON c.client_id = d.client_id WHERE a.frequency = 'POPLATEK TYDNE'), ClientInfo AS (SELECT cws.client_id, cws.gender, CASE WHEN (CAST(STRFTIME('%Y', '2026-10-01') AS INTEGER) - CAST(STRFTIME('%Y', cws.birth_date) AS INTEGER)) < 30 THEN 'Young' WHEN (CAST(STRFTIME('%Y', '2026-10-01') AS INTEGER) - CAST(STRFTIME('%Y', cws.birth_date) AS INTEGER)) < 60 THEN 'Middle-aged' ELSE 'Senior' END AS age_group, di.A3 AS region, cws.account_id FROM CustomerWeeklyStatements AS cws JOIN district AS di ON di.district_id = cws.district_id), LoanAndTransactionData AS (SELECT ci.client_id, ci.gender, ci.age_group, ci.region, ci.account_id, (SELECT COUNT(*) FROM card AS cd JOIN disp AS dd ON dd.disp_id = cd.disp_id WHERE dd.client_id = ci.client_id) AS cards_count, (SELECT COUNT(*) FROM loan AS l JOIN account AS aa ON aa.account_id = l.account_id JOIN disp AS dd2 ON dd2.account_id = aa.account_id WHERE dd2.client_id = ci.client_id) AS loans_count, (SELECT COALESCE(SUM(l.amount), 0) FROM loan AS l JOIN account AS aa ON aa.account_id = l.account_id JOIN disp AS dd3 ON dd3.account_id = aa.account_id WHERE dd3.client_id = ci.client_id) AS loans_amount, (SELECT COUNT(*) FROM trans AS t JOIN account AS aa ON aa.account_id = t.account_id JOIN disp AS dd4 ON dd4.account_id = aa.account_id WHERE dd4.client_id = ci.client_id AND t.type IN ('PRIJEM', 'VYDAJ')) AS trans_count, (SELECT COALESCE(SUM(CASE WHEN t.type = 'PRIJEM' THEN t.amount ELSE 0 END), 0) - COALESCE(SUM(CASE WHEN t.type = 'VYDAJ' THEN t.amount ELSE 0 END), 0) FROM trans AS t JOIN account AS aa ON aa.account_id = t.account_id JOIN disp AS dd5 ON dd5.account_id = aa.account_id WHERE dd5.client_id = ci.client_id AND t.type IN ('PRIJEM', 'VYDAJ')) AS net_balance FROM ClientInfo AS ci) SELECT COUNT(DISTINCT client_id) AS total_weekly
-- truncated
```

### bird_0097

- 数据库：financial
- 分类：other_result_mismatch
- 细分类：join_semantics
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'ClientLoanInfo:d.client_id、d.type、a.frequency | ClientTransactions:d.client_id | ClientCards:d.client_id'], ['predicted_group_by', 'client_loan_info:dp.client_id | transactions:dp.client_id | cards:dp.client_id'], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=8;predicted=10'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:560144e95b89ac689e5ed4c0570330ba7f96e32410658d0021e7137e18135555;2:accepted:']]
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
WITH disponent_po_obratu AS (SELECT DISTINCT d.client_id, a.account_id FROM disp AS d JOIN account AS a ON d.account_id = a.account_id WHERE d.type = 'DISPONENT' AND a.frequency = 'POPLATEK PO OBRATU'), client_loan_info AS (SELECT dp.client_id, COUNT(l.loan_id) AS loan_count, AVG(l.amount) AS avg_loan_amount, SUM(CASE WHEN l.status = 'A' THEN 1 ELSE 0 END) AS active_loans, SUM(CASE WHEN l.status = 'B' THEN 1 ELSE 0 END) AS completed_loans FROM disponent_po_obratu AS dp LEFT JOIN loan AS l ON l.account_id = dp.account_id GROUP BY dp.client_id), transactions AS (SELECT dp.client_id, COUNT(t.trans_id) AS transaction_count, SUM(CASE WHEN t.type = 'PRIJEM' THEN t.amount ELSE 0 END) AS total_income, SUM(CASE WHEN t.type = 'VYDAJ' THEN t.amount ELSE 0 END) AS total_expense, MAX(t.date) AS last_transaction_date FROM disponent_po_obratu AS dp LEFT JOIN trans AS t ON t.account_id = dp.account_id GROUP BY dp.client_id), cards AS (SELECT dp.client_id, COUNT(c.card_id) AS card_count, GROUP_CONCAT(DISTINCT c.type) AS card_types FROM disponent_po_obratu AS dp LEFT JOIN disp AS d2 ON d2.account_id = dp.account_id LEFT JOIN card AS c ON c.disp_id = d2.disp_id GROUP BY dp.client_id), base AS (SELECT cl.client_id AS client_id, cl.gender AS gender, cl.birth_date AS birth_date, di.A2 AS district_name, di.A3 AS region, COALESCE(li.loan_count, 0) AS loan_count, COALESCE(li.avg_loan_amount, 0) AS avg_loan_amount, COALESCE(li.active_loans, 0) AS active_loans, COALESCE(li.completed_loans, 0) AS completed_loans, COALESCE(tx.transaction_count, 0) AS transaction_count, COALESCE(tx.total_income, 0) AS total_income, COALESCE(tx.total_expense, 0) AS total_expense, COALESCE(tx.total_income, 0) - COALESCE(tx.total_expense, 0) AS net_balance, tx.last_transaction_date AS last_transaction_date, COALESCE(cd.card_count, 0) AS card_count, cd.card_types AS card_types, CASE WHEN COALESCE(li.loan_count, 0) > 0 AND COALESCE(cd.card_count, 0) > 0 THEN 'Full Service' WHEN COALESCE(li.loan_count, 0) > 0 AND COAL
-- truncated
```

### bird_0100

- 数据库：financial
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', 'loan_flags:s.client_id'], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=4;predicted=5'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '']]
- 错误类别：None
- 脱敏错误：None
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：None
- 度量覆盖：1.0
- 种子表：['account', 'disp', 'loan', 'order', 'trans', 'card', 'client', 'district']
- 引用表：['account', 'client', 'disp', 'district', 'loan']
- 投影：['total_female_clients', 'avg_age_at_account_opening', 'clients_with_loans', 'clients_with_good_loans', 'clients_with_debt', 'earliest_account_year', 'latest_account_year']
- 聚合：['count', 'avg', 'sum', 'min', 'max']
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH sokolov_female_owners AS (SELECT DISTINCT c.client_id, CAST(STRFTIME('%Y', a.date) AS INTEGER) - CAST(STRFTIME('%Y', c.birth_date) AS INTEGER) AS age_at_opening, CAST(STRFTIME('%Y', a.date) AS INTEGER) AS account_year, a.account_id FROM client AS c JOIN district AS d ON c.district_id = d.district_id JOIN disp AS dp ON dp.client_id = c.client_id JOIN account AS a ON a.account_id = dp.account_id WHERE c.gender = 'F' AND CAST(STRFTIME('%Y', c.birth_date) AS INTEGER) < 1950 AND d.A2 = 'Sokolov' AND dp.type = 'OWNER'), loan_flags AS (SELECT s.client_id, MAX(CASE WHEN l.status IN ('A', 'D') THEN 1 ELSE 0 END) AS has_loan, MAX(CASE WHEN l.status = 'A' THEN 1 ELSE 0 END) AS has_good_loan, MAX(CASE WHEN l.status = 'D' THEN 1 ELSE 0 END) AS has_debt FROM sokolov_female_owners AS s JOIN loan AS l ON l.account_id = s.account_id GROUP BY s.client_id) SELECT COUNT(DISTINCT s.client_id) AS total_female_clients, ROUND(AVG(s.age_at_opening), 2) AS avg_age_at_account_opening, COALESCE(SUM(CASE WHEN lf.has_loan = 1 THEN 1 ELSE 0 END), 0) AS clients_with_loans, COALESCE(SUM(CASE WHEN lf.has_good_loan = 1 THEN 1 ELSE 0 END), 0) AS clients_with_good_loans, COALESCE(SUM(CASE WHEN lf.has_debt = 1 THEN 1 ELSE 0 END), 0) AS clients_with_debt, MIN(s.account_year) AS earliest_account_year, MAX(s.account_year) AS latest_account_year FROM sokolov_female_owners AS s LEFT JOIN loan_flags AS lf ON lf.client_id = s.client_id
```

### bird_0104

- 数据库：financial
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=5;predicted=5'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:undefined_column:sha256:e86552c8b27dcbfec4ff47e050ad5b27942473d943a4cf5c6b129385e36a4029;2:empty_result:sha256:76875bf6b5876d91fa5a9493c76acd17ba6c818e2094b43c0b5c1fd72404ad85;3:no_progress:sha256:76875bf6b5876d91fa5a9493c76acd17ba6c818e2094b43c0b5c1fd72404ad85;4:kept_candidate:no_progress']]
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
WITH TransactionDetails AS (SELECT t.trans_id, t.account_id, t.date AS transaction_date, t.amount, t.balance, a.date AS account_opening_date, a.district_id, d.A2 AS district_name, d.A3 AS region FROM trans AS t JOIN account AS a ON t.account_id = a.account_id JOIN district AS d ON a.district_id = d.district_id WHERE t.trans_id = 840 AND STRFTIME('%Y', t.date) = '1998' AND STRFTIME('%m', t.date) = '10' AND STRFTIME('%d', t.date) = '14'), AccountOwners AS (SELECT td.trans_id, td.account_id, td.transaction_date, td.amount, td.balance, td.account_opening_date, td.district_id, td.district_name, td.region, c.client_id, c.gender, c.birth_date FROM TransactionDetails AS td LEFT JOIN disp AS dp ON dp.account_id = td.account_id AND dp.type = 'OWNER' LEFT JOIN client AS c ON dp.client_id = c.client_id) SELECT ao.account_id AS account_id, ao.account_opening_date AS account_opening_date, ao.transaction_date AS transaction_date, CAST((STRFTIME('%Y', ao.transaction_date) - STRFTIME('%Y', ao.account_opening_date)) * 365.25 + (STRFTIME('%m', ao.transaction_date) - STRFTIME('%m', ao.account_opening_date)) * 30.44 + (STRFTIME('%d', ao.transaction_date) - STRFTIME('%d', ao.account_opening_date)) AS INTEGER) AS days_account_open_before_transaction, ao.amount AS amount, ao.balance AS balance, ao.district_name AS district_name, ao.region AS region, ao.client_id AS client_id, CASE ao.gender WHEN 'M' THEN 'Male' WHEN 'F' THEN 'Female' ELSE 'Unknown' END AS gender_full, CAST((STRFTIME('%Y', ao.transaction_date) - STRFTIME('%Y', ao.birth_date)) - (CASE WHEN STRFTIME('%m-%d', ao.transaction_date) < STRFTIME('%m-%d', ao.birth_date) THEN 1 ELSE 0 END) AS INTEGER) AS age_at_transaction, (SELECT COUNT(*) FROM trans AS t2 WHERE t2.account_id = ao.account_id AND t2.date <= ao.transaction_date) AS total_transactions_to_date, (SELECT COUNT(*) FROM card AS cd JOIN disp AS dp2 ON cd.disp_id = dp2.disp_id WHERE dp2.account_id = ao.account_id) AS cards_issued, CASE WHEN EXISTS(SELECT 1 FROM loan AS l WHER
-- truncated
```

### bird_0105

- 数据库：financial
- 分类：other_result_mismatch
- 细分类：join_semantics
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'ClientsInDistrict:d.district_id'], ['predicted_group_by', 'clients_in_district:c.district_id | trans_stats:t.account_id'], ['aggregation_only_in_cte', 'district_info,clients_in_district,trans_stats'], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=5;predicted=5'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:fd03f67c9ac452fe60dcefa3e4d54c79586d986a5f5cdb2f37f20ba8af9f33a6;2:accepted:']]
- 错误类别：None
- 脱敏错误：None
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
WITH target_loan AS (SELECT loan_id, account_id, date AS loan_date FROM loan WHERE date = '1994-08-25'), loan_account AS (SELECT tl.loan_id, tl.loan_date, a.account_id, a.district_id, a.date AS account_open_date FROM target_loan AS tl JOIN account AS a ON a.account_id = tl.account_id), district_info AS (SELECT d.district_id, d.A2 AS district_name, d.A3 AS region, d.A11 AS avg_salary, d.A13 AS unemployment_rate_1995, RANK() OVER (ORDER BY d.A11 DESC) AS salary_rank, RANK() OVER (ORDER BY d.A13 DESC) AS unemployment_rank FROM district AS d), clients_in_district AS (SELECT c.district_id, COUNT(DISTINCT c.client_id) AS num_clients, SUM(CASE WHEN c.gender = 'M' THEN 1 ELSE 0 END) AS male_clients, SUM(CASE WHEN c.gender = 'F' THEN 1 ELSE 0 END) AS female_clients, AVG((JULIANDAY('1994-08-25') - JULIANDAY(c.birth_date)) / 365.25) AS avg_client_age FROM client AS c GROUP BY c.district_id), trans_stats AS (SELECT t.account_id, COUNT(*) AS transactions_before_loan, SUM(CASE WHEN t.type = 'PRIJEM' THEN t.amount ELSE 0 END) AS total_income_before_loan FROM trans AS t JOIN loan_account AS la ON la.account_id = t.account_id WHERE t.date < la.loan_date GROUP BY t.account_id) SELECT la.district_id AS district_id, di.district_name AS district_name, di.region AS region, la.account_open_date AS account_open_date, CAST(JULIANDAY(la.loan_date) - JULIANDAY(la.account_open_date) AS INTEGER) AS days_account_open_before_loan, di.avg_salary AS avg_salary, di.unemployment_rate_1995 AS unemployment_rate_1995, di.salary_rank AS salary_rank, di.unemployment_rank AS unemployment_rank, cid.num_clients AS num_clients, cid.male_clients AS male_clients, cid.female_clients AS female_clients, cid.avg_client_age AS avg_client_age, COALESCE(ts.transactions_before_loan, 0) AS transactions_before_loan, COALESCE(ts.total_income_before_loan, 0) AS total_income_before_loan FROM loan_account AS la JOIN district_info AS di ON di.district_id = la.district_id JOIN clients_in_district AS cid ON cid.district_id = la
-- truncated
```

### bird_0106

- 数据库：financial
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', 'trans_stats'], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=8;predicted=9'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '']]
- 错误类别：None
- 脱敏错误：None
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：None
- 度量覆盖：None
- 种子表：['client', 'card', 'district', 'disp', 'trans', 'account', 'loan', 'order']
- 引用表：['account', 'card', 'client', 'disp', 'district', 'loan', 'order', 'trans']
- 投影：['client_id', 'card_id', 'card_type', 'gender', 'client_age', 'district_name', 'region', 'trans_id', 'largest_transaction_amount', 'transaction_type', 'transaction_date', 'balance_after_transaction', 'transaction_category', 'loan_status', 'loan_amount', 'order_id', 'bank_to']
- 聚合：[]
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH card_client AS (SELECT c.client_id, ca.card_id, ca.type AS card_type, c.gender, c.birth_date, c.district_id FROM card AS ca JOIN disp AS d ON ca.disp_id = d.disp_id JOIN client AS c ON d.client_id = c.client_id WHERE ca.issued = '1996-10-21'), client_accounts AS (SELECT cc.client_id, cc.card_id, cc.card_type, cc.gender, cc.birth_date, cc.district_id, a.account_id FROM card_client AS cc JOIN disp AS d2 ON d2.client_id = cc.client_id JOIN account AS a ON a.account_id = d2.account_id), trans_stats AS (SELECT ca.client_id, ca.card_id, ca.card_type, ca.gender, ca.birth_date, ca.district_id, t.trans_id, t.amount, t.type, t.date, t.balance, RANK() OVER (PARTITION BY ca.client_id ORDER BY t.amount DESC) AS amount_rank FROM client_accounts AS ca JOIN trans AS t ON t.account_id = ca.account_id) SELECT ts.client_id AS client_id, ts.card_id AS card_id, ts.card_type AS card_type, ts.gender AS gender, CAST(STRFTIME('%Y', '2026-10-01') AS INTEGER) - CAST(STRFTIME('%Y', ts.birth_date) AS INTEGER) AS client_age, di.A2 AS district_name, di.A3 AS region, ts.trans_id AS trans_id, ts.amount AS largest_transaction_amount, ts.type AS transaction_type, ts.date AS transaction_date, ts.balance AS balance_after_transaction, CASE WHEN ts.amount >= 10000 THEN 'High Value' WHEN ts.amount >= 5000 THEN 'Medium Value' ELSE 'Low Value' END AS transaction_category, CASE WHEN NOT l.loan_id IS NULL THEN 'Has Loan' ELSE 'No Loan' END AS loan_status, l.amount AS loan_amount, o.order_id AS order_id, o.bank_to AS bank_to FROM trans_stats AS ts JOIN district AS di ON di.district_id = ts.district_id LEFT JOIN client_accounts AS ca2 ON ca2.client_id = ts.client_id LEFT JOIN loan AS l ON l.account_id = ca2.account_id LEFT JOIN "order" AS o ON o.account_id = ca2.account_id WHERE ts.amount_rank = 1 LIMIT 1
```

### bird_0111

- 数据库：financial
- 分类：other_result_mismatch
- 细分类：join_semantics
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'ClientInfo:d.account_id | AccountActivity:account_id | LoanStatus:account_id'], ['predicted_group_by', 'AccountActivity:ai.account_id | LoanStatus:ai.account_id'], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=5;predicted=9'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:dcbfd9c402c8acaf68d4179380c8252975923483775189f17287634c7b4e8af4;2:accepted:']]
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
WITH AccountsInLitomerice1996 AS (SELECT a.account_id, a.date AS open_date FROM account AS a JOIN district AS d ON a.district_id = d.district_id WHERE d.A2 = 'Litomerice' AND STRFTIME('%Y', a.date) = '1996'), ClientInfo AS (SELECT ai.account_id, c.client_id, c.gender, c.birth_date FROM AccountsInLitomerice1996 AS ai JOIN disp AS dp ON ai.account_id = dp.account_id JOIN client AS c ON dp.client_id = c.client_id), AccountActivity AS (SELECT ai.account_id, COUNT(t.trans_id) AS txn_count, SUM(CASE WHEN t.type = 'PRIJEM' THEN t.amount ELSE 0 END) AS deposit_amount FROM AccountsInLitomerice1996 AS ai LEFT JOIN trans AS t ON ai.account_id = t.account_id AND STRFTIME('%Y', t.date) = '1996' GROUP BY ai.account_id), LoanStatus AS (SELECT ai.account_id, COUNT(l.loan_id) AS loan_count, SUM(l.amount) AS loan_amount FROM AccountsInLitomerice1996 AS ai LEFT JOIN loan AS l ON ai.account_id = l.account_id GROUP BY ai.account_id) SELECT COUNT(DISTINCT ai.account_id) AS total_accounts, SUM(CASE WHEN cc.client_count > 1 THEN 1 ELSE 0 END) AS accounts_with_multiple_clients, AVG(2026 - CAST(STRFTIME('%Y', ci.birth_date) AS INTEGER)) AS average_client_age, SUM(CASE WHEN ci.gender = 'M' THEN 1 ELSE 0 END) AS total_male_clients, SUM(CASE WHEN ci.gender = 'F' THEN 1 ELSE 0 END) AS total_female_clients, SUM(COALESCE(aa.txn_count, 0)) AS total_transactions_in_1996, SUM(COALESCE(aa.deposit_amount, 0)) AS total_deposits_in_1996, SUM(COALESCE(ls.loan_count, 0)) AS total_loans, AVG(ls.loan_amount) AS avg_loan_amount, SUM(CASE WHEN ls.loan_count > 0 THEN 1 ELSE 0 END) AS accounts_with_loans, AVG(CASE WHEN CAST(STRFTIME('%m', ai.open_date) AS INTEGER) BETWEEN 1 AND 3 THEN 100.0 ELSE 0 END) AS percent_opened_q1, AVG(CASE WHEN CAST(STRFTIME('%m', ai.open_date) AS INTEGER) BETWEEN 4 AND 6 THEN 100.0 ELSE 0 END) AS percent_opened_q2, AVG(CASE WHEN CAST(STRFTIME('%m', ai.open_date) AS INTEGER) BETWEEN 7 AND 9 THEN 100.0 ELSE 0 END) AS percent_opened_q3, AVG(CASE WHEN CAST(STRFTIME('%m', ai.open_date) AS 
-- truncated
```

### bird_0113

- 数据库：financial
- 分类：other_result_mismatch
- 细分类：response_shape
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'ClientTransactions:LC.client_id、LC.birth_date、LC.age_at_loan、d.A2、d.A3 | CardInfo:LC.client_id'], ['predicted_group_by', 'outer:lc.client_id、lc.birth_date、lc.loan_date、di.A2、di.A3、ci.card_count、ci.card_types、pl.previous_loans | CardInfo:d.client_id'], ['aggregation_only_in_cte', ''], ['missing_output_labels', 'None'], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=11;predicted=11'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:undefined_column:sha256:0cd204b116cd0c8318ad5b6577213ccdc2c61b4225a087076a5cf606873ef430;2:cartesian_product:sha256:b0537b8cb145ad6fe818336e55eb5f389bf76a1487fab6f9e97cada1b78501a4;3:no_progress:sha256:b0537b8cb145ad6fe818336e55eb5f389bf76a1487fab6f9e97cada1b78501a4;4:kept_candidate:no_progress']]
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
- 分组：['lc.client_id', 'lc.birth_date', 'lc.loan_date', 'di.A2', 'di.A3', 'ci.card_count', 'ci.card_types', 'pl.previous_loans']
- 电商规则：[]
- 串库表：[]

```sql
WITH LoanClient AS (SELECT c.client_id, c.birth_date, c.district_id, l.date AS loan_date, l.amount AS loan_amount FROM loan AS l JOIN account AS a ON l.account_id = a.account_id JOIN disp AS d ON a.account_id = d.account_id AND d.type = 'OWNER' JOIN client AS c ON d.client_id = c.client_id WHERE l.amount = 98832 AND l.date = '1996-01-03'), ClientTransactions AS (SELECT t.trans_id, t.account_id, t.type, t.amount, t.balance FROM trans AS t JOIN disp AS d ON t.account_id = d.account_id JOIN LoanClient AS lc ON d.client_id = lc.client_id WHERE t.date < lc.loan_date), CardInfo AS (SELECT d.client_id, GROUP_CONCAT(ca.type) AS card_types, COUNT(*) AS card_count FROM card AS ca JOIN disp AS d ON ca.disp_id = d.disp_id JOIN LoanClient AS lc ON d.client_id = lc.client_id GROUP BY d.client_id), PrevLoans AS (SELECT COUNT(*) AS previous_loans FROM loan AS l JOIN account AS a ON l.account_id = a.account_id JOIN disp AS d ON a.account_id = d.account_id JOIN LoanClient AS lc ON d.client_id = lc.client_id) SELECT lc.birth_date AS birth_date, CAST(STRFTIME('%Y', lc.loan_date) AS INTEGER) - CAST(STRFTIME('%Y', lc.birth_date) AS INTEGER) AS age_at_loan, di.A2 AS district_name, di.A3 AS region, COUNT(ct.trans_id) AS transaction_count, SUM(CASE WHEN ct.type = 'PRIJEM' THEN ct.amount ELSE 0 END) AS total_income, SUM(CASE WHEN ct.type = 'VYDAJ' THEN ct.amount ELSE 0 END) AS total_expense, ROUND(CAST(SUM(CASE WHEN ct.type = 'VYDAJ' THEN ct.amount ELSE 0 END) AS REAL) * 100.0 / NULLIF(SUM(CASE WHEN ct.type = 'PRIJEM' THEN ct.amount ELSE 0 END), 0), 2) AS expense_to_income_ratio, MAX(ct.balance) AS max_balance, MIN(ct.balance) AS min_balance, ci.card_count AS card_count, ci.card_types AS card_types, pl.previous_loans AS previous_loans FROM LoanClient AS lc JOIN district AS di ON lc.district_id = di.district_id LEFT JOIN ClientTransactions AS ct ON 1 = 1 LEFT JOIN CardInfo AS ci ON lc.client_id = ci.client_id CROSS JOIN PrevLoans AS pl GROUP BY lc.client_id, lc.birth_date, lc.loan_date, di.A2
-- truncated
```

### bird_0119

- 数据库：financial
- 分类：sql_error
- 细分类：circuit_breaker
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'AccountStats:a.account_id | ClientDetails:a.account_id | LoanInfo:a.account_id'], ['predicted_group_by', 'TransStats:t.account_id | ClientStats:d.account_id | LoanStats:l.account_id'], ['aggregation_only_in_cte', 'TransStats,ClientStats,LoanStats'], ['missing_output_labels', 'Rural'], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=8;predicted=5'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:2013c7cd838e3f3a287fe3ca8b37670ebf77877d40939671de35ef755caa9a3f;2:no_progress:sha256:2013c7cd838e3f3a287fe3ca8b37670ebf77877d40939671de35ef755caa9a3f']]
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
  SELECT a.account_id, a.district_id
  FROM account a
  WHERE a.frequency = 'POPLATEK PO OBRATU'
    AND STRFTIME('%Y', a.date) = '1993'
),
TransStats AS (
  SELECT t.account_id,
         COUNT(*) AS transaction_count,
         SUM(CASE WHEN t.type = 'PRIJEM' THEN t.amount ELSE 0 END) -
         SUM(CASE WHEN t.type = 'VYDAJ' THEN t.amount ELSE 0 END) AS net_cash_flow,
         AVG(t.balance) AS balance_volatility
  FROM trans t
  WHERE t.type IN ('PRIJEM','VYDAJ')
  GROUP BY t.account_id
),
ClientStats AS (
  SELECT d.account_id,
         COUNT(DISTINCT c.client_id) AS client_count,
         GROUP_CONCAT(DISTINCT c.gender) AS owner_gender,
         AVG(CAST(STRFTIME('%Y','2026-10-01') AS INTEGER) - CAST(STRFTIME('%Y', c.birth_date) AS INTEGER)) AS avg_client_age
  FROM disp d
  JOIN client c ON c.client_id = d.client_id
  GROUP BY d.account_id
),
LoanStats AS (
  SELECT l.account_id,
         COUNT(*) AS loan_count,
         SUM(l.amount) AS total_loan_amount,
         AVG(l.duration) AS avg_loan_duration_months,
         SUM(CASE WHEN l.status = 'A' THEN 1 ELSE 0 END) AS running_loans,
         SUM(CASE WHEN l.status = 'B' THEN 1 ELSE 0 END) AS finished_loans,
         SUM(CASE WHEN l.status = 'C' THEN 1 ELSE 0 END) AS defaulted_loans
  FROM loan l
  GROUP BY l.account_id
)
SELECT
  ai.account_id AS account_id,
  d.A2 AS district_name,
  d.A3 AS district_region,
  d.A5 AS urbanization_category,
  COALESCE(ts.transaction_count, 0) AS transaction_count,
  COALESCE(ts.net_cash_flow, 0) AS net_cash_flow,
  COALESCE(ts.balance_volatility, 0) AS balance_volatility,
  COALESCE(cs.client_count, 0) AS client_count,
  cs.owner_gender AS owner_gender,
  cs.avg_client_age AS avg_client_age,
  COALESCE(ls.loan_count, 0) AS loan_count,
  COALESCE(ls.total_loan_amount, 0) AS total_loan_amount,
  ls.avg_loan_duration_months AS avg_loan_duration_months,
  COALESCE(ls.running_loans, 0) AS running_loans,
  COALESCE(ls.finished_loans, 0) AS finished_loans,
  
-- truncated
```

### bird_0121

- 数据库：financial
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'TransactionStats:t.account_id | LoanInfo:l.account_id'], ['predicted_group_by', 'TransactionStats:t.account_id | LoanInfo:l.account_id'], ['aggregation_only_in_cte', 'TransactionStats,LoanInfo'], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=8;predicted=6'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:undefined_column:sha256:d90fe8642067e578404a9040aa841c0a709d4bd78dbf6c65a00a0b5c7805d84a;2:accepted:']]
- 错误类别：None
- 脱敏错误：None
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
WITH AccountsInPrachatice AS (SELECT a.account_id, a.date AS opening_date, a.district_id FROM account AS a JOIN district AS d ON a.district_id = d.district_id WHERE d.A2 = 'Prachatice'), OwnerInfo AS (SELECT dp.account_id, c.gender, c.birth_date FROM disp AS dp JOIN client AS c ON c.client_id = dp.client_id WHERE dp.type = 'OWNER'), TransactionStats AS (SELECT t.account_id, COUNT(*) AS transaction_count, SUM(CASE WHEN t.type = 'PRIJEM' THEN t.amount ELSE 0 END) AS total_income, SUM(CASE WHEN t.type = 'VYDAJ' THEN t.amount ELSE 0 END) AS total_expense, MAX(t.balance) AS max_balance FROM trans AS t WHERE t.type IN ('PRIJEM', 'VYDAJ') GROUP BY t.account_id), LoanInfo AS (SELECT l.account_id, COUNT(*) AS loan_count, SUM(l.amount) AS total_loan_amount, CASE WHEN SUM(CASE WHEN l.status = 'A' THEN 1 ELSE 0 END) > 0 THEN 'Has Active Loan' WHEN SUM(CASE WHEN l.status = 'B' THEN 1 ELSE 0 END) > 0 THEN 'Has Completed Loan' WHEN SUM(CASE WHEN l.status = 'C' THEN 1 ELSE 0 END) > 0 THEN 'Has Defaulted Loan' WHEN SUM(CASE WHEN l.status = 'D' THEN 1 ELSE 0 END) > 0 THEN 'Has Loan' ELSE 'No Loans' END AS loan_status FROM loan AS l GROUP BY l.account_id), Profile AS (SELECT ap.account_id AS account_id, ap.opening_date AS opening_date, d.A2 AS district_name, d.A3 AS region, oi.gender AS gender, CAST(STRFTIME('%Y', '2026-10-01') AS INTEGER) - CAST(STRFTIME('%Y', oi.birth_date) AS INTEGER) AS client_age, COALESCE(ts.transaction_count, 0) AS transaction_count, COALESCE(ts.total_income, 0) AS total_income, COALESCE(ts.total_expense, 0) AS total_expense, COALESCE(ts.total_income, 0) - COALESCE(ts.total_expense, 0) AS net_balance, COALESCE(ts.max_balance, 0) AS max_balance, COALESCE(li.loan_count, 0) AS loan_count, COALESCE(li.total_loan_amount, 0) AS total_loan_amount, COALESCE(li.loan_status, 'No Loans') AS loan_status, CASE WHEN COALESCE(ts.transaction_count, 0) >= 50 THEN 'High Activity' WHEN COALESCE(ts.transaction_count, 0) >= 20 THEN 'Medium Activity' WHEN COALESCE(ts.transaction_cou
-- truncated
```

### bird_0122

- 数据库：financial
- 分类：other_result_mismatch
- 细分类：join_semantics
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'DistrictStats:d.district_id、d.A2、d.A3、d.A11、d.A12'], ['predicted_group_by', 'DistrictStats:a.district_id'], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=8;predicted=6'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '']]
- 错误类别：None
- 脱敏错误：None
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：None
- 度量覆盖：None
- 种子表：['loan', 'district', 'account', 'client', 'card', 'disp', 'order', 'trans']
- 引用表：['account', 'client', 'disp', 'district', 'loan', 'trans']
- 投影：['loan_id', 'district_name', 'region', 'gender', 'birth_date', 'loan_amount', 'loan_duration_months', 'status_description', 'district_avg_salary', 'unemployment_rate_1995', 'district_total_loans', 'district_avg_loan_amount', 'district_problematic_loans', 'district_loan_rank', 'total_transactions']
- 聚合：['count']
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH LoanStats AS (SELECT l.loan_id, l.account_id, l.amount, l.duration, l.status, a.district_id, c.client_id, c.gender, c.birth_date FROM loan AS l JOIN account AS a ON l.account_id = a.account_id JOIN disp AS d ON d.account_id = a.account_id AND d.type = 'OWNER' JOIN client AS c ON d.client_id = c.client_id WHERE l.loan_id = 4990), DistrictStats AS (SELECT a.district_id, COUNT(l.loan_id) AS district_total_loans, AVG(l.amount) AS district_avg_loan_amount, SUM(CASE WHEN l.status IN ('B', 'D') THEN 1 ELSE 0 END) AS district_problematic_loans FROM loan AS l JOIN account AS a ON l.account_id = a.account_id GROUP BY a.district_id), Ranked AS (SELECT l.loan_id, a.district_id, l.amount, RANK() OVER (PARTITION BY a.district_id ORDER BY l.amount DESC) AS district_loan_rank FROM loan AS l JOIN account AS a ON l.account_id = a.account_id) SELECT ls.loan_id, di.A2 AS district_name, di.A3 AS region, ls.gender, ls.birth_date, ls.amount AS loan_amount, ls.duration AS loan_duration_months, CASE ls.status WHEN 'A' THEN 'Running-OK' WHEN 'B' THEN 'Running-Issues' WHEN 'C' THEN 'Finished-No Issues' WHEN 'D' THEN 'Finished-Issues' END AS status_description, di.A11 AS district_avg_salary, di.A13 AS unemployment_rate_1995, ds.district_total_loans, ds.district_avg_loan_amount, ds.district_problematic_loans, r.district_loan_rank, (SELECT COUNT(*) FROM trans AS t WHERE t.account_id = ls.account_id) AS total_transactions FROM LoanStats AS ls JOIN district AS di ON ls.district_id = di.district_id JOIN DistrictStats AS ds ON ls.district_id = ds.district_id JOIN Ranked AS r ON ls.loan_id = r.loan_id AND ls.district_id = r.district_id
```

### bird_0123

- 数据库：financial
- 分类：other_result_mismatch
- 细分类：join_semantics
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'LoanStatistics:account_id | TransactionSummary:account_id'], ['predicted_group_by', 'loan_stats:l.account_id | trans_summary:t.account_id'], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=5;predicted=5'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:389a83a9a87f02ec527d85dd3792abc9288e9b5603a5c37d90cd729c6ac23a1b;2:cartesian_product:sha256:da9178436f2f8d21d7d9c95ffdd8cb5e526e005ae50af6873f57de8797365a97;3:accepted:']]
- 错误类别：None
- 脱敏错误：None
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
WITH national_avg AS (SELECT AVG(A11) AS avg_salary FROM district), high_salary_districts AS (SELECT d.district_id, d.A2 AS district_name, d.A3 AS region_name FROM district AS d WHERE d.A11 > (SELECT avg_salary FROM national_avg)), loan_stats AS (SELECT l.account_id, MAX(l.amount) AS max_loan_amount, AVG(l.amount) AS avg_loan_amount, COUNT(l.loan_id) AS loan_count FROM loan AS l GROUP BY l.account_id HAVING MAX(l.amount) > 300000), trans_summary AS (SELECT t.account_id, COUNT(t.trans_id) AS transaction_count, SUM(CASE WHEN t.type = 'PRIJEM' THEN t.amount ELSE 0 END) AS total_income, SUM(CASE WHEN t.type = 'VYDAJ' THEN t.amount ELSE 0 END) AS total_expense FROM trans AS t WHERE t.type IN ('PRIJEM', 'VYDAJ') GROUP BY t.account_id), owner_info AS (SELECT dp.account_id, c.gender, CAST(STRFTIME('%Y', '2026-10-01') AS INTEGER) - CAST(STRFTIME('%Y', c.birth_date) AS INTEGER) AS age FROM disp AS dp JOIN client AS c ON dp.client_id = c.client_id WHERE dp.type = 'OWNER') SELECT a.account_id AS account_id, hsd.district_name AS district_name, hsd.region_name AS region_name, ls.max_loan_amount AS max_loan_amount, ls.avg_loan_amount AS avg_loan_amount, ls.loan_count AS loan_count, oi.gender AS gender, oi.age AS age, CASE WHEN ts.total_income IS NULL THEN 'Low Income' WHEN ts.total_income >= 100000 THEN 'High Income' WHEN ts.total_income >= 50000 THEN 'Medium Income' ELSE 'Low Income' END AS income_category, COALESCE(ts.transaction_count, 0) AS transaction_count, CASE WHEN ts.total_income IS NULL OR ts.total_income = 0 THEN NULL ELSE ROUND((ts.total_income - ts.total_expense) * 1.0 / ts.total_income, 4) END AS savings_ratio, RANK() OVER (PARTITION BY hsd.region_name ORDER BY ls.max_loan_amount DESC) AS region_loan_rank FROM account AS a JOIN high_salary_districts AS hsd ON a.district_id = hsd.district_id JOIN loan_stats AS ls ON a.account_id = ls.account_id JOIN owner_info AS oi ON a.account_id = oi.account_id LEFT JOIN trans_summary AS ts ON a.account_id = ts.account_id WHERE ts.
-- truncated
```
