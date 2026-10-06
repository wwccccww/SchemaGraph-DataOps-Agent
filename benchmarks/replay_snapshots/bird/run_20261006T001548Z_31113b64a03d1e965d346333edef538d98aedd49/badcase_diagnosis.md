# 外部问数诊断

- 来源：bird
- 模型：deepseek-chat
- Prompt：text-to-sql-generic-v15
- 执行准确率：0.14
- 匹配：7
- SQL 错误：8
- 可执行率：0.84
- 方言错误率：0.0
- 上下文召回：1.0
- 引用表召回：0.9971428571428571
- 维度覆盖：1.0
- 实体覆盖：1.0
- 度量覆盖：1.0
- 结果不一致：35
- 电商规则命中用例：0
- 串库用例：0
- 这是注册库上的模型执行，不是 Gold-only，也不是官方 TPC-DS 分数。

## 未匹配

### bird_0002

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:3e820826c67db8f8e44ae1f47ba0a46f692139f6034741e513da01819098654d;2:projection_mismatch:sha256:d1ee74af35a6da2cd57c6b28666cd56f617bf280a6a6982cac99041ab451fe97;3:projection_mismatch:sha256:3e820826c67db8f8e44ae1f47ba0a46f692139f6034741e513da01819098654d;4:projection_mismatch:sha256:d1ee74af35a6da2cd57c6b28666cd56f617bf280a6a6982cac99041ab451fe97;5:projection_mismatch:sha256:3e820826c67db8f8e44ae1f47ba0a46f692139f6034741e513da01819098654d']]
- 错误类别：projection_mismatch
- 脱敏错误：projection_mismatch: charter school 语义优先使用 schools 表的 Charter 字段，不要用 frpm 的 Y/N 列
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：1.0
- 度量覆盖：1.0
- 种子表：['frpm', 'schools', 'satscores']
- 引用表：['frpm', 'satscores', 'schools']
- 投影：['Zip', 'City', 'CharterSchoolName', 'Charter Funding Type', 'Enrollment', 'PercentFRPM', 'FRPMCategory', 'YearOpened', 'CurrentStatus', 'SATTestTakers', 'TotalSATScore', 'PercentageAbove1500', 'SATRanking', 'EnrollmentRanking']
- 聚合：['sum', 'count', 'rank']
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH base AS (
  SELECT
    s.CDSCode,
    s.Zip AS Zip,
    s.City AS City,
    s.School AS CharterSchoolName,
    f."Charter Funding Type" AS "Charter Funding Type",
    f."Enrollment (K-12)" AS Enrollment,
    f."Percent (%) Eligible FRPM (K-12)" * 100 AS PercentFRPM,
    CASE
      WHEN f."Percent (%) Eligible FRPM (K-12)" >= 0.75 THEN 'High FRPM'
      WHEN f."Percent (%) Eligible FRPM (K-12)" >= 0.50 THEN 'Medium FRPM'
      ELSE 'Low FRPM'
    END AS FRPMCategory,
    CAST(strftime('%Y', s.OpenDate) AS INTEGER) AS YearOpened,
    CASE
      WHEN s.ClosedDate IS NULL OR s.ClosedDate = '' THEN 'Active'
      ELSE 'Closed'
    END AS CurrentStatus,
    sa.NumTstTakr AS SATTestTakers,
    (sa.AvgScrRead + sa.AvgScrMath + sa.AvgScrWrite) AS TotalSATScore
  FROM frpm f
  JOIN schools s ON f.CDSCode = s.CDSCode
  LEFT JOIN satscores sa ON sa.cds = s.CDSCode
  WHERE f."District Name" = 'Fresno County Office of Education'
    AND f."Charter School (Y/N)" = 1
    AND f."Enrollment (K-12)" > 0
)
SELECT
  Zip,
  City,
  CharterSchoolName,
  "Charter Funding Type",
  Enrollment,
  PercentFRPM,
  FRPMCategory,
  YearOpened,
  CurrentStatus,
  SATTestTakers,
  TotalSATScore,
  ROUND(100.0 * SUM(CASE WHEN TotalSATScore > 1500 THEN 1 ELSE 0 END) OVER () / NULLIF(COUNT(TotalSATScore) OVER (), 0), 2) AS PercentageAbove1500,
  RANK() OVER (ORDER BY TotalSATScore DESC) AS SATRanking,
  RANK() OVER (ORDER BY Enrollment DESC) AS EnrollmentRanking
FROM base
ORDER BY SATRanking, EnrollmentRanking;
```

### bird_0003

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：grouping_grain
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:03ee002b014b5c67e0b02fb326030ecdf1bbde960c2414991771b9109f0d4807;2:accepted:']]
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
WITH base AS (SELECT s.School AS SchoolName, s.County AS County, s.City AS City, TRIM(COALESCE(s.MailStreet, s.Street) || ', ' || COALESCE(s.MailCity, s.City) || ', ' || COALESCE(s.MailState, s.State) || ' ' || COALESCE(s.MailZip, s.Zip)) AS UnabbreviatedMailingAddress, s.Website AS Website, f."Enrollment (K-12)" AS Enrollment, f."FRPM Count (K-12)" AS FRPMCount, f."Free Meal Count (K-12)" * 1.0 / f."Enrollment (K-12)" AS FRPMPercentage, (COALESCE(sa.AvgScrRead, 0) + COALESCE(sa.AvgScrMath, 0) + COALESCE(sa.AvgScrWrite, 0)) AS TotalSATScore, CASE WHEN sa.cds IS NULL THEN 'No SAT Data' WHEN (COALESCE(sa.AvgScrRead, 0) + COALESCE(sa.AvgScrMath, 0) + COALESCE(sa.AvgScrWrite, 0)) < 1200 THEN 'Below Average' WHEN (COALESCE(sa.AvgScrRead, 0) + COALESCE(sa.AvgScrMath, 0) + COALESCE(sa.AvgScrWrite, 0)) <= 1500 THEN 'Average' ELSE 'Above Average' END AS PerformanceCategory, CASE WHEN sa.NumTstTakr > 0 THEN sa.NumGE1500 * 1.0 / sa.NumTstTakr ELSE NULL END AS PercentHighScorers, CASE WHEN sa.cds IS NULL THEN 'No SAT Data' WHEN (COALESCE(sa.AvgScrRead, 0) + COALESCE(sa.AvgScrMath, 0) + COALESCE(sa.AvgScrWrite, 0)) < 1200 THEN 'Below Average' WHEN (COALESCE(sa.AvgScrRead, 0) + COALESCE(sa.AvgScrMath, 0) + COALESCE(sa.AvgScrWrite, 0)) <= 1500 THEN 'Average' ELSE 'Above Average' END AS PerformanceClassification, s.OpenDate AS OpenDate, s.StatusType AS SchoolStatus FROM frpm AS f JOIN schools AS s ON f.CDSCode = s.CDSCode LEFT JOIN satscores AS sa ON sa.cds = s.CDSCode WHERE s.Charter = 0 AND f."Enrollment (K-12)" > 100 AND f."Enrollment (K-12)" > 0) SELECT SchoolName, County, City, UnabbreviatedMailingAddress, Website, Enrollment, FRPMCount, FRPMPercentage, TotalSATScore, PerformanceCategory, PercentHighScorers, PerformanceClassification, OpenDate, SchoolStatus FROM base ORDER BY FRPMCount DESC LIMIT 1
```

### bird_0005

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:missing_entity:sha256:71fde2b71dc1807c35a3be351a2114ca1130b8e458a9bb1fccb32e3eed0d5f89;2:empty_result:sha256:76875bf6b5876d91fa5a9493c76acd17ba6c818e2094b43c0b5c1fd72404ad85;3:no_progress:sha256:76875bf6b5876d91fa5a9493c76acd17ba6c818e2094b43c0b5c1fd72404ad85;4:kept_candidate:no_progress']]
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
WITH base AS (SELECT s.School AS SchoolName, s.City AS City, s.Virtual AS VirtualStatus, s.GSserved AS SchoolType, ss.AvgScrMath AS MathScore, ss.AvgScrRead AS ReadingScore, ss.AvgScrWrite AS WritingScore, (ss.AvgScrRead + ss.AvgScrMath + ss.AvgScrWrite) AS TotalScore, f."Enrollment (K-12)" AS Enrollment, f."Percent (%) Eligible FRPM (K-12)" AS FRPMPercentage FROM schools AS s LEFT JOIN satscores AS ss ON ss.cds = s.CDSCode JOIN frpm AS f ON f.CDSCode = s.CDSCode WHERE s.Virtual = 'Fully Virtual' AND ss.AvgScrMath > 400) SELECT SchoolName, City, VirtualStatus, SchoolType, MathScore, ReadingScore, WritingScore, TotalScore, RANK() OVER (ORDER BY MathScore DESC) AS MathRank, RANK() OVER (ORDER BY TotalScore DESC) AS TotalScoreRank, Enrollment, CASE WHEN FRPMPercentage >= 75 THEN 'High FRPM' WHEN FRPMPercentage >= 50 THEN 'Medium FRPM' ELSE 'Low FRPM' END AS PovertyLevel, FRPMPercentage FROM base ORDER BY TotalScore DESC
```

### bird_0006

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
- 种子表：['schools', 'satscores', 'frpm']
- 引用表：['frpm', 'satscores', 'schools']
- 投影：['School', 'SchoolType', 'EducationalOption', 'TestTakers', 'TotalAvgScore', 'ReadingScore', 'MathScore', 'WritingScore', 'PercentHighScorers', 'Enrollment', 'FreeReducedMealPercentage', 'StateRank', 'CountyRank', 'PovertyLevel', 'PerformanceCategory']
- 聚合：['rank']
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH base AS (SELECT s.School AS School, COALESCE(f."School Type", 'Unknown') AS SchoolType, COALESCE(f."Educational Option Type", 'Unknown') AS EducationalOption, sa.NumTstTakr AS TestTakers, (sa.AvgScrRead + sa.AvgScrMath + sa.AvgScrWrite) AS TotalAvgScore, sa.AvgScrRead AS ReadingScore, sa.AvgScrMath AS MathScore, sa.AvgScrWrite AS WritingScore, CAST(sa.NumGE1500 AS REAL) * 100.0 / NULLIF(sa.NumTstTakr, 0) AS PercentHighScorers, f."Enrollment (K-12)" AS Enrollment, CASE WHEN f."Enrollment (K-12)" > 0 THEN f."Free Meal Count (K-12)" * 100.0 / f."Enrollment (K-12)" ELSE NULL END AS FreeReducedMealPercentage, s.County AS County FROM schools AS s JOIN satscores AS sa ON sa.cds = s.CDSCode JOIN frpm AS f ON f.CDSCode = s.CDSCode WHERE s.Magnet = 1 AND sa.NumTstTakr > 500) SELECT School, SchoolType, EducationalOption, TestTakers, TotalAvgScore, ReadingScore, MathScore, WritingScore, PercentHighScorers, Enrollment, FreeReducedMealPercentage, RANK() OVER (ORDER BY TotalAvgScore DESC) AS StateRank, RANK() OVER (PARTITION BY County ORDER BY TotalAvgScore DESC) AS CountyRank, CASE WHEN FreeReducedMealPercentage >= 75 THEN 'High FRPM' WHEN FreeReducedMealPercentage >= 50 THEN 'Medium FRPM' ELSE 'Low FRPM' END AS PovertyLevel, CASE WHEN TotalAvgScore > 1500 THEN 'Above Average' WHEN TotalAvgScore >= 1200 THEN 'Average' ELSE 'Below Average' END AS PerformanceCategory FROM base ORDER BY TotalAvgScore DESC
```

### bird_0008

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
- 投影：['County', 'District', 'School', 'school_type', 'grade_level', 'frpm_count', 'enrollment', 'percent_eligible_frpm', 'num_sat_takers', 'percent_taking_sat', 'avg_reading', 'avg_math', 'avg_writing', 'total_avg_score', 'percent_scoring_over_1500', 'frpm_rank']
- 聚合：['rank']
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH base AS (SELECT frpm."County Name" AS County, frpm."District Name" AS District, frpm."School Name" AS School, frpm."School Type" AS school_type, frpm."Low Grade" || '-' || frpm."High Grade" AS grade_level, frpm."FRPM Count (K-12)" AS frpm_count, frpm."Enrollment (K-12)" AS enrollment, frpm."Percent (%) Eligible FRPM (K-12)" AS percent_eligible_frpm, satscores.NumTstTakr AS num_sat_takers, CASE WHEN frpm."Enrollment (K-12)" > 0 THEN satscores.NumTstTakr * 100.0 / frpm."Enrollment (K-12)" ELSE NULL END AS percent_taking_sat, satscores.AvgScrRead AS avg_reading, satscores.AvgScrMath AS avg_math, satscores.AvgScrWrite AS avg_writing, (satscores.AvgScrRead + satscores.AvgScrMath + satscores.AvgScrWrite) AS total_avg_score, CASE WHEN satscores.NumTstTakr > 0 THEN satscores.NumGE1500 * 100.0 / satscores.NumTstTakr ELSE NULL END AS percent_scoring_over_1500 FROM frpm JOIN schools ON frpm.CDSCode = schools.CDSCode LEFT JOIN satscores ON satscores.cds = schools.CDSCode WHERE frpm."Enrollment (K-12)" > 0) SELECT County, District, School, school_type, grade_level, frpm_count, enrollment, percent_eligible_frpm, num_sat_takers, percent_taking_sat, avg_reading, avg_math, avg_writing, total_avg_score, percent_scoring_over_1500, RANK() OVER (ORDER BY frpm_count DESC) AS frpm_rank FROM base ORDER BY frpm_count DESC LIMIT 10
```

### bird_0010

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
- 种子表：['schools', 'satscores', 'frpm']
- 引用表：['frpm', 'satscores', 'schools']
- 投影：['SchoolName', 'County', 'City', 'GradeSpan', 'ReadingScore', 'MathScore', 'WritingScore', 'TotalSATScore', 'ReadingRank', 'FRPMCount', 'FRPMPercentage', 'Enrollment', 'PercentScoring1500Plus', 'SchoolType', 'PovertyLevel']
- 聚合：['rank']
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH base AS (SELECT s.School AS SchoolName, s.County AS County, s.City AS City, s.GSserved AS GradeSpan, ss.AvgScrRead AS ReadingScore, ss.AvgScrMath AS MathScore, ss.AvgScrWrite AS WritingScore, (ss.AvgScrRead + ss.AvgScrMath + ss.AvgScrWrite) AS TotalSATScore, ss.NumTstTakr, ss.NumGE1500, f."FRPM Count (K-12)" AS FRPMCount, f."Percent (%) Eligible FRPM (K-12)" AS FRPMPercentage, f."Enrollment (K-12)" AS Enrollment, s.Charter, f."School Type" AS SchoolType FROM schools AS s JOIN satscores AS ss ON ss.cds = s.CDSCode LEFT JOIN frpm AS f ON f.CDSCode = s.CDSCode WHERE ss.NumTstTakr > 10) SELECT SchoolName, County, City, GradeSpan, ReadingScore, MathScore, WritingScore, TotalSATScore, RANK() OVER (ORDER BY ReadingScore DESC) AS ReadingRank, FRPMCount, FRPMPercentage, Enrollment, CASE WHEN Enrollment > 0 THEN ROUND(CAST(NumGE1500 AS REAL) * 100 / Enrollment, 2) ELSE NULL END AS PercentScoring1500Plus, SchoolType, CASE WHEN FRPMPercentage >= 75 THEN 'High FRPM' WHEN FRPMPercentage >= 50 THEN 'Medium FRPM' ELSE 'Low FRPM' END AS PovertyLevel FROM base ORDER BY ReadingScore DESC LIMIT 1
```

### bird_0011

- 数据库：california_schools
- 分类：sql_error
- 细分类：circuit_breaker
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:f014be20a6ea4068cb93f6166d824e53c084688b4999505ef687f64e26a73cc1;2:no_progress:sha256:f014be20a6ea4068cb93f6166d824e53c084688b4999505ef687f64e26a73cc1']]
- 错误类别：no_progress
- 脱敏错误：修复没有改变症状，已标记 no_progress 并熔断
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
    f.CDSCode AS CDSCode,
    f."School Name" AS "School Name",
    f."County Name" AS "County Name",
    f."Enrollment (K-12)" AS TotalEnrollment,
    f."Percent (%) Eligible FRPM (K-12)" * 100 AS FRPMPercentage,
    CASE
      WHEN f."Percent (%) Eligible FRPM (K-12)" * 100 >= 75 THEN 'High'
      WHEN f."Percent (%) Eligible FRPM (K-12)" * 100 >= 50 THEN 'Medium'
      ELSE 'Low'
    END AS FRPMCategory,
    CASE s.Charter WHEN 1 THEN 'Yes' WHEN 0 THEN 'No' ELSE 'Unknown' END AS IsCharterSchool,
    ss.NumTstTakr AS SATTestTakers,
    (COALESCE(ss.AvgScrRead,0) + COALESCE(ss.AvgScrMath,0) + COALESCE(ss.AvgScrWrite,0)) AS TotalSATScore,
    CASE
      WHEN ss.NumTstTakr IS NULL OR ss.NumTstTakr = 0 THEN NULL
      ELSE ss.NumGE1500 * 100.0 / ss.NumTstTakr
    END AS PercentageStudentsOver1500
  FROM frpm f
  JOIN schools s ON s.CDSCode = f.CDSCode
  LEFT JOIN satscores ss ON ss.cds = s.CDSCode
  WHERE f."Enrollment (K-12)" > 500
    AND f."Enrollment (K-12)" > 0
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
FROM base
WHERE FRPMPercentage > 60
   OR (PercentageStudentsOver1500 IS NOT NULL AND PercentageStudentsOver1500 > 30)
ORDER BY "County Name", CountyEnrollmentRank;
```

### bird_0012

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', 'county_avg:County'], ['aggregation_only_in_cte', 'county_avg,ranked'], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=3'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '']]
- 错误类别：None
- 脱敏错误：None
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：1.0
- 度量覆盖：1.0
- 种子表：['schools', 'frpm', 'satscores']
- 引用表：['frpm', 'satscores', 'schools']
- 投影：['SchoolName', 'County', 'City', 'school_type', 'excellence_rate', 'eligible_free_rate', 'county_rank', 'avg_eligible_free_rate', 'free_meal_category']
- 聚合：[]
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH base AS (SELECT s.School AS SchoolName, s.County AS County, s.City AS City, s.SOCType AS school_type, (COALESCE(sat.AvgScrRead, 0) + COALESCE(sat.AvgScrMath, 0) + COALESCE(sat.AvgScrWrite, 0)) * 1.0 AS sat_total, f."Free Meal Count (K-12)" * 1.0 / f."Enrollment (K-12)" AS eligible_free_rate FROM schools AS s JOIN frpm AS f ON f.CDSCode = s.CDSCode LEFT JOIN satscores AS sat ON sat.cds = s.CDSCode WHERE f."Enrollment (K-12)" > 0), filtered AS (SELECT *, sat_total * 1.0 / 2400 AS excellence_rate FROM base WHERE sat_total * 1.0 / 2400 > 0.30), county_avg AS (SELECT County, AVG(eligible_free_rate) AS avg_eligible_free_rate FROM filtered GROUP BY County), ranked AS (SELECT fi.SchoolName, fi.County, fi.City, fi.school_type, fi.excellence_rate, fi.eligible_free_rate, RANK() OVER (PARTITION BY fi.County ORDER BY fi.eligible_free_rate DESC) AS county_rank, ca.avg_eligible_free_rate, CASE WHEN fi.eligible_free_rate >= 0.75 THEN 'High FRPM' WHEN fi.eligible_free_rate >= 0.50 THEN 'Medium FRPM' ELSE 'Low FRPM' END AS free_meal_category FROM filtered AS fi JOIN county_avg AS ca ON ca.County = fi.County) SELECT SchoolName, County, City, school_type, excellence_rate, eligible_free_rate, county_rank, avg_eligible_free_rate, free_meal_category FROM ranked WHERE county_rank = 1 ORDER BY eligible_free_rate DESC LIMIT 1
```

### bird_0013

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：grouping_grain
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:undefined_column:sha256:193e083b1f49bf950db32a492052fe6b8a4d096840cbbd2c9fd1e599e18520f4;2:accepted:']]
- 错误类别：None
- 脱敏错误：None
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
WITH base AS (SELECT s.School AS "School Name", s.Phone AS "Contact Number", s.City AS "City", CASE s.Charter WHEN 1 THEN 'Yes' WHEN 0 THEN 'No' ELSE 'Unknown' END AS "Charter School", sc.NumGE1500 AS "High Scorers", sc.NumTstTakr AS "Test Takers", CASE WHEN sc.NumTstTakr > 0 THEN sc.NumGE1500 * 1.0 / sc.NumTstTakr ELSE NULL END AS "SAT Excellence Rate", CASE WHEN f."Enrollment (K-12)" > 0 THEN f."Free Meal Count (K-12)" * 1.0 / f."Enrollment (K-12)" ELSE NULL END AS "Poverty Rate" FROM schools AS s JOIN satscores AS sc ON sc.cds = s.CDSCode LEFT JOIN frpm AS f ON f.CDSCode = s.CDSCode WHERE sc.NumTstTakr > 0) SELECT ROW_NUMBER() OVER (ORDER BY "SAT Excellence Rate" DESC) AS "SAT Excellence Rank", "School Name", "SAT Excellence Rate", "High Scorers" || '/' || "Test Takers" AS "High Scorers/Test Takers", "Contact Number", "City", "Charter School", "Poverty Rate", CASE WHEN "Poverty Rate" IS NULL THEN 'Unknown' WHEN "Poverty Rate" >= 0.75 THEN 'High FRPM' WHEN "Poverty Rate" >= 0.50 THEN 'Medium FRPM' ELSE 'Low FRPM' END AS "Poverty Category" FROM base ORDER BY "SAT Excellence Rate" DESC LIMIT 3
```

### bird_0018

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'outer:ss."County Name"'], ['predicted_group_by', 'outer:"County Name"'], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:undefined_column:sha256:1ba68692240228a2601a8db01e0b129f3917de268ee9012a67a9b1a9180ba047;2:empty_result:sha256:76875bf6b5876d91fa5a9493c76acd17ba6c818e2094b43c0b5c1fd72404ad85;3:no_progress:sha256:76875bf6b5876d91fa5a9493c76acd17ba6c818e2094b43c0b5c1fd72404ad85;4:kept_candidate:no_progress']]
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
WITH base AS (SELECT sc.CDSCode, sc.County AS "County Name", ss.NumTstTakr, (ss.AvgScrRead + ss.AvgScrMath + ss.AvgScrWrite) AS total_score, ss.NumGE1500, f."Percent (%) Eligible FRPM (K-12)" AS frpm_pct, (JULIANDAY('2026-10-01') - JULIANDAY(sc.OpenDate)) / 365.25 AS school_age FROM schools AS sc JOIN satscores AS ss ON ss.cds = sc.CDSCode JOIN frpm AS f ON f.CDSCode = sc.CDSCode WHERE sc.Charter = 1 AND sc.FundingType = 'Directly Funded' AND sc.County = 'Fresno' AND ss.NumTstTakr <= 250) SELECT COUNT(*) AS TotalSchools, "County Name", AVG(NumTstTakr) AS AvgTestTakers, AVG(total_score) AS AvgTotalScore, AVG(CASE WHEN NumTstTakr > 0 THEN 100.0 * NumGE1500 / NumTstTakr END) AS AvgPercentScoring1500Plus, AVG(frpm_pct) AS AvgFRPMPercentage, AVG(school_age) AS AvgSchoolAgeInYears, SUM(CASE WHEN NumTstTakr < 50 THEN 1 ELSE 0 END) AS SchoolsWithUnder50Testers, SUM(CASE WHEN NumTstTakr >= 50 AND NumTstTakr <= 100 THEN 1 ELSE 0 END) AS SchoolsWith50To100Testers, SUM(CASE WHEN NumTstTakr > 100 AND NumTstTakr <= 250 THEN 1 ELSE 0 END) AS SchoolsWith100To250Testers FROM base GROUP BY "County Name"
```

### bird_0019

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=3;predicted=4'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '']]
- 错误类别：None
- 脱敏错误：None
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
WITH top_school AS (SELECT s.cds FROM satscores AS s JOIN schools AS sc ON sc.CDSCode = s.cds WHERE sc.StatusType = 'Active' AND s.NumTstTakr >= 10 ORDER BY s.AvgScrMath DESC LIMIT 1) SELECT sc.School AS "Top Math School", sc.Phone AS "Phone Number", sc.Website AS "Website", sa.AvgScrMath AS "Math Score", sa.AvgScrRead AS "Reading Score", sa.AvgScrWrite AS "Writing Score", (sa.AvgScrRead + sa.AvgScrMath + sa.AvgScrWrite) AS "Total Score", CASE sc.Charter WHEN 1 THEN 'Yes' WHEN 0 THEN 'No' ELSE 'Unknown' END AS "Is Charter School", f."Enrollment (K-12)" AS "Enrollment", (f."Free Meal Count (K-12)" * 1.0 / f."Enrollment (K-12)") AS "% Free/Reduced Price Meals", (SELECT COUNT(*) FROM satscores) AS "Total Schools in SAT Dataset", (SELECT AVG(AvgScrMath) FROM satscores) AS "Average Math Score Across All Schools" FROM top_school AS t JOIN schools AS sc ON sc.CDSCode = t.cds JOIN satscores AS sa ON sa.cds = t.cds JOIN frpm AS f ON f.CDSCode = t.cds WHERE f."Enrollment (K-12)" > 0
```

### bird_0020

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', 'agg'], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '']]
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
- 聚合：[]
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH base AS (SELECT s.CDSCode, s.School, s.District, s.Charter, f."Enrollment (K-12)" AS enrollment, f."Free Meal Count (K-12)" AS free_meal, f."District Name" AS district_name, (sa.AvgScrRead + sa.AvgScrMath + sa.AvgScrWrite) AS sat_total FROM schools AS s LEFT JOIN frpm AS f ON f.CDSCode = s.CDSCode LEFT JOIN satscores AS sa ON sa.cds = s.CDSCode WHERE s.County = 'Amador' AND s.GSserved LIKE '%12%'), agg AS (SELECT COUNT(DISTINCT CDSCode) AS TotalSchools, AVG(enrollment) AS AvgEnrollment, SUM(CASE WHEN Charter = 1 THEN 1 ELSE 0 END) AS CharterSchools, SUM(CASE WHEN Charter = 0 THEN 1 ELSE 0 END) AS NonCharterSchools, AVG(CASE WHEN enrollment > 0 THEN free_meal * 1.0 / enrollment END) * 100 AS AvgFRPMPercentage, COUNT(DISTINCT district_name) AS DistrictCount, AVG(sat_total) AS AvgSATScore, MAX(CASE WHEN sat_total > 1500 THEN 1 ELSE 0 END) AS MaxPercentAbove1500, SUM(CASE WHEN enrollment > 0 AND free_meal * 1.0 / enrollment >= 0.75 THEN 1 ELSE 0 END) AS HighPovertySchools FROM base) SELECT a.TotalSchools, a.AvgEnrollment, a.CharterSchools, a.NonCharterSchools, a.AvgFRPMPercentage, a.DistrictCount, a.AvgSATScore, a.MaxPercentAbove1500, (SELECT School FROM base WHERE NOT enrollment IS NULL ORDER BY enrollment DESC LIMIT 1) AS LargestSchool, a.HighPovertySchools FROM agg AS a
```

### bird_0021

- 数据库：california_schools
- 分类：sql_error
- 细分类：circuit_breaker
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'CategoryBreakdown:FreeMealCategory'], ['predicted_group_by', ''], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=3;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:not_read_only:sha256:bfb824e1489412bc1dc345919873a103819ed0768987a15f2433392516d78343;2:no_progress:sha256:bfb824e1489412bc1dc345919873a103819ed0768987a15f2433392516d78343']]
- 错误类别：no_progress
- 脱敏错误：只允许单条只读 SQLite 查询
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
WITH base AS (SELECT f.CDSCode, f."Free Meal Count (K-12)" AS free_meals, f."FRPM Count (K-12)" AS frpm_meals, f."Enrollment (K-12)" AS enrollment, f."Free Meal Count (K-12)" * 1.0 / f."Enrollment (K-12)" AS free_pct, f."FRPM Count (K-12)" * 1.0 / f."Enrollment (K-12)" AS frpm_pct, s.Charter, (COALESCE(sat.AvgScrRead, 0) + COALESCE(sat.AvgScrMath, 0) + COALESCE(sat.AvgScrWrite, 0)) AS sat_total, sat.cds AS sat_cds, CASE WHEN f."FRPM Count (K-12)" * 1.0 / f."Enrollment (K-12)" >= 0.75 THEN 'High FRPM' WHEN f."FRPM Count (K-12)" * 1.0 / f."Enrollment (K-12)" >= 0.50 THEN 'Medium FRPM' ELSE 'Low FRPM' END AS frpm_category FROM frpm AS f JOIN schools AS s ON f.CDSCode = s.CDSCode LEFT JOIN satscores AS sat ON sat.cds = s.CDSCode WHERE f."County Name" = 'Los Angeles' AND f."Enrollment (K-12)" > 0 AND f."Free Meal Count (K-12)" > 500 AND f."FRPM Count (K-12)" < 700) SELECT COUNT(*) AS TotalSchools, ROUND(AVG(free_meals), 2) AS AvgFreeMeals, ROUND(AVG(frpm_meals), 2) AS AvgTotalFRPM, ROUND(AVG(free_pct), 4) AS AvgFreePercentage, ROUND(AVG(frpm_pct), 4) AS AvgFRPMPercentage, SUM(CASE WHEN Charter = 1 THEN 1 ELSE 0 END) AS CharterSchoolCount, SUM(CASE WHEN Charter = 0 THEN 1 ELSE 0 END) AS NonCharterSchoolCount, ROUND(AVG(CASE WHEN NOT sat_cds IS NULL THEN sat_total END), 2) AS AvgSATScore, SUM(CASE WHEN sat_cds IS NULL THEN 1 ELSE 0 END) AS SchoolsWithoutSATData, GROUP_CONCAT(frpm_category || ':' || cnt, '; ') AS FreeMealCategoryBreakdown FROM (SELECT *, COUNT(*) OVER (PARTITION BY frpm_category) AS cnt FROM base)
```

### bird_0031

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:d6f109df1e65270e0d4304e77bc7e7302c1a4646b31efa624c4b6dc9b8ae06de;2:accepted:']]
- 错误类别：None
- 脱敏错误：None
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：1.0
- 度量覆盖：None
- 种子表：['schools', 'frpm', 'satscores']
- 引用表：['frpm', 'satscores', 'schools']
- 投影：['EnrollmentRank', 'School Name', 'District Name', 'County Name', 'TotalEnrollment', 'FreeMealCount', 'EligibleFreeRate', 'City', 'SchoolType', 'GradeSpan', 'Website', 'SATTestTakers', 'AvgReadingScore', 'AvgMathScore', 'AvgWritingScore', 'PercentAbove1500SAT']
- 聚合：[]
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH ranked AS (SELECT f.CDSCode, f."School Name" AS school_name, f."District Name" AS district_name, f."County Name" AS county_name, f."Enrollment (K-12)" AS total_enrollment, f."Free Meal Count (K-12)" AS free_meal_count, f."School Type" AS school_type, f."Low Grade" AS low_grade, f."High Grade" AS high_grade, ROW_NUMBER() OVER (ORDER BY f."Enrollment (K-12)" DESC) AS rn FROM frpm AS f WHERE NOT f."Enrollment (K-12)" IS NULL) SELECT r.rn AS "EnrollmentRank", r.school_name AS "School Name", r.district_name AS "District Name", r.county_name AS "County Name", r.total_enrollment AS "TotalEnrollment", r.free_meal_count AS "FreeMealCount", ROUND(r.free_meal_count * 1.0 / r.total_enrollment, 4) AS "EligibleFreeRate", s.City AS "City", r.school_type AS "SchoolType", r.low_grade || '-' || r.high_grade AS "GradeSpan", s.Website AS "Website", sa.NumTstTakr AS "SATTestTakers", sa.AvgScrRead AS "AvgReadingScore", sa.AvgScrMath AS "AvgMathScore", sa.AvgScrWrite AS "AvgWritingScore", CASE WHEN sa.NumTstTakr IS NULL THEN NULL ELSE ROUND(sa.NumGE1500 * 1.0 / sa.NumTstTakr * 100, 2) END AS "PercentAbove1500SAT" FROM ranked AS r JOIN schools AS s ON s.CDSCode = r.CDSCode LEFT JOIN satscores AS sa ON sa.cds = r.CDSCode WHERE r.rn IN (10, 11) ORDER BY r.rn
```

### bird_0032

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：grouping_grain
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '']]
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
WITH base AS (SELECT s.CDSCode, s.School, s.County, s.District, s.SOCType, f."Enrollment (K-12)" AS Enrollment, f."FRPM Count (K-12)" AS FRPMCount, f."Free Meal Count (K-12)" AS FreeMealCount, f."Free Meal Count (K-12)" * 1.0 / f."Enrollment (K-12)" AS EligibilityRate, sa.NumTstTakr AS SATTestTakers, sa.AvgScrRead AS AvgReading, sa.AvgScrMath AS AvgMath, sa.AvgScrWrite AS AvgWriting, (sa.AvgScrRead + sa.AvgScrMath + sa.AvgScrWrite) AS TotalSATScore, sa.NumGE1500 AS NumGE1500 FROM frpm AS f JOIN schools AS s ON f.CDSCode = s.CDSCode LEFT JOIN satscores AS sa ON sa.cds = s.CDSCode WHERE s.SOC = '66' AND f."Enrollment (K-12)" > 0 AND f."Low Grade" = 'K' AND f."High Grade" = '12' ORDER BY f."FRPM Count (K-12)" DESC LIMIT 5) SELECT ROW_NUMBER() OVER (ORDER BY FRPMCount DESC) AS FRPMRank, School, County, District, SOCType, Enrollment, FRPMCount, ROUND(EligibilityRate, 4) AS EligibilityRate, CASE WHEN EligibilityRate >= 0.75 THEN 'High FRPM' WHEN EligibilityRate >= 0.50 THEN 'Medium FRPM' ELSE 'Low FRPM' END AS EligibilityCategory, SATTestTakers, AvgReading, AvgMath, AvgWriting, TotalSATScore, CASE WHEN TotalSATScore IS NULL THEN NULL ELSE ROUND(NumGE1500 * 1.0 / SATTestTakers, 4) END AS HighSATScorerRate, CASE WHEN SATTestTakers IS NULL OR Enrollment IS NULL THEN NULL ELSE ROUND(SATTestTakers * 1.0 / Enrollment, 4) END AS SATParticipationRate FROM base ORDER BY FRPMCount DESC
```

### bird_0045

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：join_semantics
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'DistrictAverages:s.District'], ['predicted_group_by', 'distavg:s.District'], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=4;predicted=4'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '']]
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
WITH base AS (SELECT s.School AS School, sat.AvgScrWrite AS AvgScrWrite, sat.AvgScrRead AS AvgScrRead, sat.AvgScrMath AS AvgScrMath, (sat.AvgScrRead + sat.AvgScrMath + sat.AvgScrWrite) AS TotalSATScore, sat.NumTstTakr AS NumTstTakr, f."Enrollment (K-12)" AS "Enrollment (K-12)", f."Percent (%) Eligible FRPM (K-12)" * 100 AS FRPMPercentage, s.District AS District, CASE WHEN f."Enrollment (K-12)" > 0 THEN CAST(sat.NumTstTakr AS REAL) * 100 / f."Enrollment (K-12)" ELSE NULL END AS PercentageTakingSAT FROM schools AS s JOIN frpm AS f ON f.CDSCode = s.CDSCode LEFT JOIN satscores AS sat ON sat.cds = s.CDSCode WHERE s.AdmFName1 = 'Ricci' AND s.AdmLName1 = 'Ulrich' AND f."Enrollment (K-12)" > 0), distavg AS (SELECT s.District AS District, AVG(sat.AvgScrWrite) AS DistrictAvgWriteScore FROM schools AS s JOIN satscores AS sat ON sat.cds = s.CDSCode GROUP BY s.District) SELECT b.School AS School, b.AvgScrWrite AS AvgScrWrite, b.AvgScrRead AS AvgScrRead, b.AvgScrMath AS AvgScrMath, b.TotalSATScore AS TotalSATScore, b.NumTstTakr AS NumTstTakr, b."Enrollment (K-12)" AS "Enrollment (K-12)", b.FRPMPercentage AS FRPMPercentage, RANK() OVER (ORDER BY b.AvgScrWrite DESC) AS WriteScoreRank, RANK() OVER (ORDER BY b.TotalSATScore DESC) AS TotalScoreRank, d.DistrictAvgWriteScore AS DistrictAvgWriteScore, CASE WHEN b.AvgScrWrite > d.DistrictAvgWriteScore THEN 'Above District Average' WHEN b.AvgScrWrite < d.DistrictAvgWriteScore THEN 'Below District Average' ELSE 'At District Average' END AS ComparisonToDistrictAvg, (b.AvgScrWrite - d.DistrictAvgWriteScore) AS DifferenceFromDistrictAvg, b.PercentageTakingSAT AS PercentageTakingSAT FROM base AS b LEFT JOIN distavg AS d ON d.District = b.District ORDER BY b.School
```

### bird_0055

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：response_shape
- 症状：[['missing_projections', 'Metric,Ratio'], ['extra_projections', "ROUND(MAX(CASE WHEN county = 'Colusa' THEN total_enrollment END) * 1.0 / NULLIF(NULLIF(MAX(CASE WHEN county = 'Humboldt' THEN total_enrollment END), 0), 0), 4),Total Enrollment"], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', 'county_metrics:s.County'], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=1;predicted=0'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:f642cb27535d001dbd80d6514b9ba1435a2908827230bf8ad5ba2a5af85615f4;2:projection_mismatch:sha256:1609d4acaa850f6c4da1d43b2d93a00d33a1e224538b756ac029964574d01f9c;3:projection_mismatch:sha256:f642cb27535d001dbd80d6514b9ba1435a2908827230bf8ad5ba2a5af85615f4;4:projection_mismatch:sha256:ea7102912ab256cbfb836529cb7e26e35e35e01104c60b31e797fecaf420c911;5:projection_mismatch:sha256:f642cb27535d001dbd80d6514b9ba1435a2908827230bf8ad5ba2a5af85615f4']]
- 错误类别：projection_mismatch
- 脱敏错误：projection_mismatch: 不要额外输出列 Total Enrollment、ROUND(MAX(CASE WHEN county = <literal> THEN total_enrollment END) * 1.0 / NULLIF(NULLIF(MAX(CASE WHEN county = <literal> THEN total_enrollment END), 0), 0), 4)；冻结契约仅 Metric、Ratio（问句措辞冲突时以契约为准）
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：1.0
- 度量覆盖：1.0
- 种子表：['frpm', 'schools', 'satscores']
- 引用表：['frpm', 'satscores', 'schools']
- 投影：['Total Enrollment', "ROUND(MAX(CASE WHEN county = 'Colusa' THEN total_enrollment END) * 1.0 / NULLIF(NULLIF(MAX(CASE WHEN county = 'Humboldt' THEN total_enrollment END), 0), 0), 4)"]
- 聚合：['max']
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH county_metrics AS (
  SELECT
    s.County AS county,
    COUNT(DISTINCT s.CDSCode) AS total_schools,
    SUM(CASE WHEN s.Charter = 1 THEN 1 ELSE 0 END) AS charter_schools,
    SUM(CASE WHEN f."Free Meal Count (K-12)" * 1.0 / NULLIF(f."Enrollment (K-12)", 0) >= 0.75 THEN 1 ELSE 0 END) AS high_free_meal_schools,
    AVG(CASE WHEN sa.AvgScrRead IS NOT NULL THEN sa.AvgScrRead + sa.AvgScrMath + sa.AvgScrWrite END) AS avg_sat_score,
    SUM(f."Free Meal Count (K-12)") AS total_free_meal,
    SUM(f."Enrollment (K-12)") AS total_enrollment
  FROM schools s
  LEFT JOIN frpm f ON f.CDSCode = s.CDSCode
  LEFT JOIN satscores sa ON sa.cds = s.CDSCode
  WHERE s.County IN ('Colusa', 'Humboldt')
  GROUP BY s.County
)
SELECT 'Total Schools' AS Metric,
       ROUND(MAX(CASE WHEN county = 'Colusa' THEN total_schools END) * 1.0 /
             NULLIF(MAX(CASE WHEN county = 'Humboldt' THEN total_schools END), 0), 4) AS Ratio
FROM county_metrics
UNION ALL
SELECT 'Charter Schools',
       ROUND(MAX(CASE WHEN county = 'Colusa' THEN charter_schools END) * 1.0 /
             NULLIF(MAX(CASE WHEN county = 'Humboldt' THEN charter_schools END), 0), 4)
FROM county_metrics
UNION ALL
SELECT 'High Free Meal Eligibility Schools',
       ROUND(MAX(CASE WHEN county = 'Colusa' THEN high_free_meal_schools END) * 1.0 /
             NULLIF(MAX(CASE WHEN county = 'Humboldt' THEN high_free_meal_schools END), 0), 4)
FROM county_metrics
UNION ALL
SELECT 'Average SAT Score',
       ROUND(MAX(CASE WHEN county = 'Colusa' THEN avg_sat_score END) * 1.0 /
             NULLIF(MAX(CASE WHEN county = 'Humboldt' THEN avg_sat_score END), 0), 4)
FROM county_metrics
UNION ALL
SELECT 'Total Enrollment',
       ROUND(MAX(CASE WHEN county = 'Colusa' THEN total_enrollment END) * 1.0 /
             NULLIF(MAX(CASE WHEN county = 'Humboldt' THEN total_enrollment END), 0), 4)
FROM county_metrics
```

### bird_0060

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
- 度量覆盖：None
- 种子表：['frpm', 'schools', 'satscores']
- 引用表：['frpm', 'satscores', 'schools']
- 投影：['SchoolName', 'Website', 'CharterNumber', 'FundingType', 'TotalEnrollment', 'FRPMCount', 'FRPMPercentage', 'PovertyLevel', 'EnrollmentRank', 'SATTestTakers', 'AvgReadingScore', 'AvgMathScore', 'AvgWritingScore', 'StudentsOver1500', 'PercentOver1500']
- 聚合：['rank']
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH base AS (SELECT s.School AS SchoolName, s.Website AS Website, s.CharterNum AS CharterNumber, s.FundingType AS FundingType, f."Enrollment (K-12)" AS TotalEnrollment, f."FRPM Count (K-12)" AS FRPMCount, f."Percent (%) Eligible FRPM (K-12)" AS FRPMPercentage, CASE WHEN f."Percent (%) Eligible FRPM (K-12)" >= 0.75 THEN 'High FRPM' WHEN f."Percent (%) Eligible FRPM (K-12)" >= 0.50 THEN 'Medium FRPM' ELSE 'Low FRPM' END AS PovertyLevel, sa.NumTstTakr AS SATTestTakers, sa.AvgScrRead AS AvgReadingScore, sa.AvgScrMath AS AvgMathScore, sa.AvgScrWrite AS AvgWritingScore, sa.NumGE1500 AS StudentsOver1500, CASE WHEN sa.NumTstTakr IS NULL OR sa.NumTstTakr = 0 THEN NULL ELSE ROUND(CAST(sa.NumGE1500 AS REAL) * 100.0 / sa.NumTstTakr, 2) END AS PercentOver1500 FROM schools AS s JOIN frpm AS f ON f.CDSCode = s.CDSCode LEFT JOIN satscores AS sa ON sa.cds = s.CDSCode WHERE s.County = 'San Joaquin' AND s.Virtual = 'P' AND s.Charter = 1) SELECT SchoolName, Website, CharterNumber, FundingType, TotalEnrollment, FRPMCount, FRPMPercentage, PovertyLevel, RANK() OVER (ORDER BY TotalEnrollment DESC) AS EnrollmentRank, SATTestTakers, AvgReadingScore, AvgMathScore, AvgWritingScore, StudentsOver1500, PercentOver1500 FROM base ORDER BY EnrollmentRank
```

### bird_0061

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
- 度量覆盖：None
- 种子表：['frpm', 'schools', 'satscores']
- 引用表：['frpm', 'satscores', 'schools']
- 投影：['CDSCode', 'School', 'City', 'EnrollmentK12', 'FRPMCount', 'FRPMPercent', 'FRPMCategory', 'SizeRank', 'SATTestTakers', 'SATReadingScore', 'SATMathScore', 'SATWritingScore', 'SATTotalScore', 'PercentOver1500', 'SATPerformanceCategory', 'TotalCharterSchools', 'AvgCharterEnrollment']
- 聚合：['rank', 'count', 'avg']
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH base AS (SELECT s.CDSCode AS CDSCode, s.School AS School, s.City AS City, f."Enrollment (K-12)" AS EnrollmentK12, f."Free Meal Count (K-12)" AS FRPMCount, CASE WHEN f."Enrollment (K-12)" > 0 THEN f."Free Meal Count (K-12)" * 1.0 / f."Enrollment (K-12)" ELSE NULL END AS FRPMPercent, sat.NumTstTakr AS SATTestTakers, sat.AvgScrRead AS SATReadingScore, sat.AvgScrMath AS SATMathScore, sat.AvgScrWrite AS SATWritingScore, (COALESCE(sat.AvgScrRead, 0) + COALESCE(sat.AvgScrMath, 0) + COALESCE(sat.AvgScrWrite, 0)) AS SATTotalScore, CASE WHEN sat.NumTstTakr IS NULL THEN NULL ELSE sat.NumGE1500 * 1.0 / sat.NumTstTakr END AS PercentOver1500 FROM schools AS s JOIN frpm AS f ON f.CDSCode = s.CDSCode LEFT JOIN satscores AS sat ON sat.cds = s.CDSCode WHERE s.Charter = 1 AND s.City = 'Hickman' AND f."District Type" = 'Elementary School District') SELECT CDSCode, School, City, EnrollmentK12, FRPMCount, FRPMPercent, CASE WHEN FRPMPercent >= 0.75 THEN 'High FRPM' WHEN FRPMPercent >= 0.50 THEN 'Medium FRPM' ELSE 'Low FRPM' END AS FRPMCategory, RANK() OVER (ORDER BY EnrollmentK12 DESC) AS SizeRank, SATTestTakers, SATReadingScore, SATMathScore, SATWritingScore, SATTotalScore, PercentOver1500, CASE WHEN SATTestTakers IS NULL THEN 'No SAT Data' WHEN SATTotalScore < 1200 THEN 'Below Average' WHEN SATTotalScore <= 1500 THEN 'Average' ELSE 'Above Average' END AS SATPerformanceCategory, COUNT(*) OVER () AS TotalCharterSchools, AVG(EnrollmentK12) OVER () AS AvgCharterEnrollment FROM base ORDER BY SizeRank
```

### bird_0062

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：join_semantics
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'CountyStats:County'], ['predicted_group_by', 'county_stats:f."County Name"'], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=3;predicted=4'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:7b4bcaa3b2d7a9409d8c6cb8e0e073074be292d6d72cdcc3bf6a026f04d09303;2:cartesian_product:sha256:4b4789054b9500275654833d3b52aff93dcfdee809f16d64feba72b2991cb801;3:join_not_on_graph:sha256:01faff7bfb778b409e627e4f1adf745a782ee948d2c8753c843884cdcba09205;4:kept_candidate:join_not_on_graph']]
- 错误类别：None
- 脱敏错误：None
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：1.0
- 度量覆盖：1.0
- 种子表：['frpm', 'schools', 'satscores']
- 引用表：['frpm', 'satscores', 'schools']
- 投影：['CDSCode', 'School', 'District', 'County', 'Enrollment', 'FreeMealCount', 'FreePercentage', 'FreeCategory', 'CountyRank', 'TotalSchools', 'LowFreeSchools', 'CountyAvgFreePercent', 'PctLowFreeInCounty', 'LATotalLowFree']
- 聚合：['rank']
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH base AS (SELECT s.CDSCode AS CDSCode, s.School AS School, s.District AS District, f."County Name" AS County, f."Enrollment (K-12)" AS Enrollment, f."Free Meal Count (K-12)" AS FreeMealCount, (f."Free Meal Count (K-12)" * 1.0 / f."Enrollment (K-12)") AS FreePercentage FROM schools AS s JOIN frpm AS f ON f.CDSCode = s.CDSCode LEFT JOIN satscores AS sa ON sa.cds = s.CDSCode WHERE f."County Name" = 'Los Angeles' AND s.Charter = 0 AND f."Enrollment (K-12)" > 0 AND (f."Free Meal Count (K-12)" * 1.0 / f."Enrollment (K-12)") < 0.0018), county_stats AS (SELECT f."County Name" AS County, COUNT(*) AS TotalSchools, SUM(CASE WHEN f."Enrollment (K-12)" > 0 AND (f."Free Meal Count (K-12)" * 1.0 / f."Enrollment (K-12)") < 0.0018 THEN 1 ELSE 0 END) AS LowFreeSchools, AVG(CASE WHEN f."Enrollment (K-12)" > 0 THEN f."Free Meal Count (K-12)" * 1.0 / f."Enrollment (K-12)" END) AS CountyAvgFreePercent FROM schools AS s JOIN frpm AS f ON f.CDSCode = s.CDSCode WHERE f."County Name" = 'Los Angeles' AND s.Charter = 0 GROUP BY f."County Name"), la_total AS (SELECT COUNT(*) AS LATotalLowFree FROM schools AS s JOIN frpm AS f ON f.CDSCode = s.CDSCode WHERE f."County Name" = 'Los Angeles' AND s.Charter = 0 AND f."Enrollment (K-12)" > 0 AND (f."Free Meal Count (K-12)" * 1.0 / f."Enrollment (K-12)") < 0.0018) SELECT b.CDSCode AS CDSCode, b.School AS School, b.District AS District, b.County AS County, b.Enrollment AS Enrollment, b.FreeMealCount AS FreeMealCount, b.FreePercentage AS FreePercentage, 'Low FRPM' AS FreeCategory, RANK() OVER (ORDER BY b.FreePercentage ASC) AS CountyRank, cs.TotalSchools AS TotalSchools, cs.LowFreeSchools AS LowFreeSchools, cs.CountyAvgFreePercent AS CountyAvgFreePercent, (cs.LowFreeSchools * 1.0 / cs.TotalSchools) AS PctLowFreeInCounty, lt.LATotalLowFree AS LATotalLowFree FROM base AS b JOIN county_stats AS cs ON cs.County = b.County CROSS JOIN la_total AS lt ORDER BY b.FreePercentage ASC
```

### bird_0066

- 数据库：california_schools
- 分类：sql_error
- 细分类：circuit_breaker
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'CountyStats:County'], ['predicted_group_by', ''], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=3;predicted=3'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:31acddd2e9d2eaa4c345209aece4be4de1169ec04dac390c712c43b3a4c90920;2:no_progress:sha256:31acddd2e9d2eaa4c345209aece4be4de1169ec04dac390c712c43b3a4c90920']]
- 错误类别：no_progress
- 脱敏错误：修复没有改变症状，已标记 no_progress 并熔断
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
WITH base AS (
  SELECT
    s.School AS School,
    s.OpenDate AS OpenDate,
    CAST(strftime('%Y', s.OpenDate) AS INTEGER) AS OpenYear,
    f."Enrollment (K-12)" AS Enrollment,
    f."FRPM Count (K-12)" AS FRPMCount,
    f."Percent (%) Eligible FRPM (K-12)" * 100 AS FRPMPercentage,
    f."School Type" AS SchoolType,
    sa.AvgScrRead AS AvgScrRead,
    sa.AvgScrMath AS AvgScrMath,
    sa.AvgScrWrite AS AvgScrWrite,
    (sa.AvgScrRead + sa.AvgScrMath + sa.AvgScrWrite) AS TotalSATScore
  FROM schools s
  JOIN frpm f ON f.CDSCode = s.CDSCode
  LEFT JOIN satscores sa ON sa.cds = s.CDSCode
  WHERE s.County = 'Stanislaus'
    AND s.FundingType = 'Directly Funded'
    AND CAST(strftime('%Y', s.OpenDate) AS INTEGER) BETWEEN 2000 AND 2005
    AND f."Enrollment (K-12)" > 0
),
county AS (
  SELECT
    COUNT(DISTINCT s.CDSCode) AS CountyTotalSchools,
    AVG(f."Enrollment (K-12)") AS CountyAvgEnrollment,
    AVG(f."Percent (%) Eligible FRPM (K-12)" * 100) AS CountyAvgFRPMPercent
  FROM schools s
  JOIN frpm f ON f.CDSCode = s.CDSCode
  WHERE s.County = 'Stanislaus'
    AND f."Enrollment (K-12)" > 0
)
SELECT
  b.School AS School,
  b.OpenDate AS OpenDate,
  b.OpenYear AS OpenYear,
  b.Enrollment AS Enrollment,
  b.FRPMCount AS FRPMCount,
  b.FRPMPercentage AS FRPMPercent,
  b.SchoolType AS SchoolType,
  b.AvgScrRead AS AvgScrRead,
  b.AvgScrMath AS AvgScrMath,
  b.AvgScrWrite AS AvgScrWrite,
  b.TotalSATScore AS TotalSATScore,
  c.CountyTotalSchools AS CountyTotalSchools,
  c.CountyAvgEnrollment AS CountyAvgEnrollment,
  c.CountyAvgFRPMPercent AS CountyAvgFRPMPercent,
  CASE
    WHEN b.FRPMPercentage >= 75 THEN 'High FRPM'
    WHEN b.FRPMPercentage >= 50 THEN 'Medium FRPM'
    ELSE 'Low FRPM'
  END AS FRPMStatus,
  RANK() OVER (ORDER BY b.FRPMPercentage DESC) AS FRPMRank,
  RANK() OVER (ORDER BY b.TotalSATScore DESC) AS SATScoreRank
FROM base b
CROSS JOIN county c
ORDER BY b.FRPMPercentage DESC, b.TotalSATScore DESC;
```

### bird_0069

- 数据库：california_schools
- 分类：sql_error
- 细分类：circuit_breaker
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=3;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:1bbce94e7b0564797880dc8729f6865c9cc0e49e206a90f86115aba498412861;2:no_progress:sha256:1bbce94e7b0564797880dc8729f6865c9cc0e49e206a90f86115aba498412861']]
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
WITH base AS (
  SELECT
    s.NCESDist AS "NCESDist",
    s.School AS "School",
    CASE s.Charter WHEN 1 THEN 'Yes' WHEN 0 THEN 'No' ELSE 'Unknown' END AS "SchoolType",
    s.StatusType AS "CurrentStatus",
    s.OpenDate AS "OpeningDate",
    f."Enrollment (K-12)" AS "Enrollment",
    CASE
      WHEN f."Percent (%) Eligible FRPM (K-12)" >= 0.75 THEN 'High FRPM'
      WHEN f."Percent (%) Eligible FRPM (K-12)" >= 0.50 THEN 'Medium FRPM'
      ELSE 'Low FRPM'
    END AS "PovertyLevel",
    sa.AvgScrRead AS "AvgReadingScore",
    sa.AvgScrMath AS "AvgMathScore",
    sa.AvgScrWrite AS "AvgWritingScore",
    (COALESCE(sa.AvgScrRead,0) + COALESCE(sa.AvgScrMath,0) + COALESCE(sa.AvgScrWrite,0)) AS "AvgTotalScore"
  FROM schools s
  JOIN frpm f ON f.CDSCode = s.CDSCode
  LEFT JOIN satscores sa ON sa.cds = s.CDSCode
  WHERE s.SOC LIKE '3%'
)
SELECT
  "NCESDist",
  "School",
  "SchoolType",
  "CurrentStatus",
  "OpeningDate",
  "Enrollment",
  "PovertyLevel",
  "AvgReadingScore",
  "AvgMathScore",
  "AvgWritingScore",
  "AvgTotalScore",
  RANK() OVER (ORDER BY "Enrollment" DESC) AS "EnrollmentRank"
FROM base
ORDER BY "Enrollment" DESC;
```

### bird_0077

- 数据库：california_schools
- 分类：sql_error
- 细分类：circuit_breaker
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:31acddd2e9d2eaa4c345209aece4be4de1169ec04dac390c712c43b3a4c90920;2:no_progress:sha256:31acddd2e9d2eaa4c345209aece4be4de1169ec04dac390c712c43b3a4c90920']]
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
WITH base AS (
  SELECT
    s.School AS School,
    s.City AS City,
    f."Percent (%) Eligible FRPM (K-12)" * 100 AS "Percent (%) Eligible FRPM (Ages 5-17)",
    CASE
      WHEN f."Percent (%) Eligible FRPM (K-12)" IS NULL THEN 'Unknown'
      WHEN f."Percent (%) Eligible FRPM (K-12)" >= 0.75 THEN 'High FRPM'
      WHEN f."Percent (%) Eligible FRPM (K-12)" >= 0.50 THEN 'Medium FRPM'
      ELSE 'Low FRPM'
    END AS Poverty_Level,
    CASE WHEN s.Charter = 1 THEN 'Yes' WHEN s.Charter = 0 THEN 'No' ELSE 'Unknown' END AS Is_Charter,
    sa.NumTstTakr AS "Number of SAT Test Takers",
    sa.AvgScrRead AS "Avg Reading Score",
    sa.AvgScrMath AS "Avg Math Score",
    sa.AvgScrWrite AS "Avg Writing Score",
    (COALESCE(sa.AvgScrRead,0) + COALESCE(sa.AvgScrMath,0) + COALESCE(sa.AvgScrWrite,0)) AS "Total SAT Score",
    f."FRPM Count (K-12)" AS "FRPM Count",
    f."Enrollment (K-12)" AS Enrollment
  FROM schools s
  JOIN frpm f ON f.CDSCode = s.CDSCode
  LEFT JOIN satscores sa ON sa.cds = s.CDSCode
  WHERE f."County Name" = 'Los Angeles'
    AND f."Enrollment (K-12)" > 0
    AND s.GSserved LIKE '%K-9%'
)
SELECT
  School,
  City,
  "Percent (%) Eligible FRPM (Ages 5-17)",
  Poverty_Level,
  Is_Charter,
  "Number of SAT Test Takers",
  "Avg Reading Score",
  "Avg Math Score",
  "Avg Writing Score",
  "Total SAT Score",
  RANK() OVER (ORDER BY "Percent (%) Eligible FRPM (Ages 5-17)" DESC) AS "SAT Ranking",
  "FRPM Count",
  Enrollment
FROM base
ORDER BY "Percent (%) Eligible FRPM (Ages 5-17)" DESC;
```

### bird_0078

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：join_semantics
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'outer:sbs.GSserved、sbs.school_count | SchoolsByGradeSpan:s.GSserved'], ['predicted_group_by', 'span_counts:GSserved'], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=3;predicted=3'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '']]
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
- 聚合：['count', 'avg', 'sum']
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH active AS (SELECT s.CDSCode, s.GSserved, s.City FROM schools AS s WHERE s.StatusType = 'Active' AND s.City = 'Adelanto'), span_counts AS (SELECT GSserved, COUNT(*) AS cnt FROM active GROUP BY GSserved), most_common AS (SELECT GSserved FROM span_counts ORDER BY cnt DESC, GSserved LIMIT 1), joined AS (SELECT a.CDSCode, f."Enrollment (K-12)" AS enrollment, f."Percent (%) Eligible FRPM (K-12)" AS frpm_pct, sa.AvgScrRead AS read_score, sa.AvgScrMath AS math_score, sa.AvgScrWrite AS write_score FROM active AS a JOIN most_common AS mc ON a.GSserved = mc.GSserved LEFT JOIN frpm AS f ON f.CDSCode = a.CDSCode LEFT JOIN satscores AS sa ON sa.cds = a.CDSCode) SELECT (SELECT GSserved FROM most_common) AS most_common_grade_span, COUNT(*) AS school_count, COUNT(*) AS active_schools, AVG(enrollment) AS avg_enrollment, SUM(enrollment) AS total_enrollment, AVG(frpm_pct) AS avg_frpm_percentage, SUM(CASE WHEN frpm_pct >= 75 THEN 1 ELSE 0 END) AS high_poverty_schools, SUM(CASE WHEN frpm_pct >= 50 AND frpm_pct < 75 THEN 1 ELSE 0 END) AS medium_poverty_schools, SUM(CASE WHEN frpm_pct < 50 THEN 1 ELSE 0 END) AS low_poverty_schools, AVG(read_score) AS avg_reading_score, AVG(math_score) AS avg_math_score, AVG(write_score) AS avg_writing_score FROM joined
```

### bird_0079

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'CountyStats:County'], ['predicted_group_by', 'county_stats:County'], ['aggregation_only_in_cte', 'county_stats'], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=3'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '']]
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
WITH virtual_schools AS (SELECT s.CDSCode, s.County, s.School, s.Charter, f."Enrollment (K-12)" AS enrollment, CASE WHEN f."Enrollment (K-12)" > 0 THEN f."Free Meal Count (K-12)" * 1.0 / f."Enrollment (K-12)" ELSE NULL END AS frpm_rate, (sa.AvgScrRead + sa.AvgScrMath + sa.AvgScrWrite) AS sat_total FROM schools AS s LEFT JOIN frpm AS f ON f.CDSCode = s.CDSCode LEFT JOIN satscores AS sa ON sa.cds = s.CDSCode WHERE s.Virtual = 'F' AND s.County IN ('San Diego', 'Santa Barbara')), county_stats AS (SELECT County, COUNT(*) AS amount, SUM(CASE WHEN Charter = 1 THEN 1 ELSE 0 END) AS CharterSchools, SUM(CASE WHEN Charter = 0 THEN 1 ELSE 0 END) AS RegularSchools, AVG(enrollment) AS AverageEnrollment, MAX(enrollment) AS HighestEnrollment, MIN(enrollment) AS LowestEnrollment, AVG(frpm_rate) AS AvgFreeReducedMealPercentage, AVG(sat_total) AS AverageSATScore FROM virtual_schools GROUP BY County), largest AS (SELECT County, School AS LargestVirtualSchool, ROW_NUMBER() OVER (PARTITION BY County ORDER BY enrollment DESC) AS rn FROM virtual_schools) SELECT cs.County AS County, cs.amount AS amount, cs.CharterSchools AS CharterSchools, cs.RegularSchools AS RegularSchools, cs.AverageEnrollment AS AverageEnrollment, cs.HighestEnrollment AS HighestEnrollment, cs.LowestEnrollment AS LowestEnrollment, cs.AvgFreeReducedMealPercentage AS AvgFreeReducedMealPercentage, cs.AverageSATScore AS AverageSATScore, l.LargestVirtualSchool AS LargestVirtualSchool FROM county_stats AS cs JOIN largest AS l ON l.County = cs.County AND l.rn = 1 ORDER BY cs.amount DESC
```

### bird_0087

- 数据库：california_schools
- 分类：sql_error
- 细分类：circuit_breaker
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', ''], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:f981187cf89957f241de6ca1d67e076a071161d6083bfc2a2ab6628192898f1a;2:no_progress:sha256:f981187cf89957f241de6ca1d67e076a071161d6083bfc2a2ab6628192898f1a']]
- 错误类别：no_progress
- 脱敏错误：修复没有改变症状，已标记 no_progress 并熔断
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：1.0
- 度量覆盖：None
- 种子表：['schools', 'frpm', 'satscores']
- 引用表：['schools']
- 投影：['AdmEmail1', 'AdmEmail2']
- 聚合：[]
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
SELECT AdmEmail1, AdmEmail2
FROM schools
WHERE County = 'San Bernardino'
  AND City = 'San Bernardino'
  AND District LIKE '%Unified%'
  AND OpenDate BETWEEN '2009-01-01' AND '2010-12-31'
  AND GSserved LIKE '%Intermediate/Middle%';
```

### bird_0092

- 数据库：financial
- 分类：other_result_mismatch
- 细分类：join_semantics
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'DistrictStats:d.district_id、d.A2、d.A3、d.A11 | AccountActivity:a.district_id'], ['predicted_group_by', 'district_stats:td.district_id、td.region'], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=5;predicted=8'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '']]
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
- 聚合：['count', 'sum', 'avg']
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH district_avg_salary /* 1. 每个 district 的平均工资（A11 为平均工资） */ AS (SELECT district_id, A3 AS region, A11 AS avg_salary FROM district), qualified_districts /* 2. 筛选平均工资在 6000-10000 的 district */ AS (SELECT district_id, region, avg_salary FROM district_avg_salary WHERE avg_salary BETWEEN 6000 AND 10000), ranked_districts /* 3. 每个 region 内按平均工资排名，取前 3 */ AS (SELECT district_id, region, avg_salary, ROW_NUMBER() OVER (PARTITION BY region ORDER BY avg_salary DESC) AS rn FROM qualified_districts), top3_districts AS (SELECT district_id, region, avg_salary FROM ranked_districts WHERE rn <= 3), female_clients /* 4. 女性客户及其账户、贷款信息 */ AS (SELECT c.client_id, c.birth_date, c.district_id FROM client AS c WHERE c.gender = 'F'), female_accounts /* 5. 女性客户拥有的账户（账户持有人 OWNER） */ AS (SELECT DISTINCT d.client_id, a.account_id, a.district_id FROM disp AS d JOIN account AS a ON d.account_id = a.account_id JOIN female_clients AS fc ON d.client_id = fc.client_id WHERE d.type = 'OWNER'), female_loans /* 6. 女性客户的贷款 */ AS (SELECT l.loan_id, l.account_id, l.amount, l.status FROM loan AS l JOIN female_accounts AS fa ON l.account_id = fa.account_id), district_stats /* 7. 每个合格 district 的女性客户统计 */ AS (SELECT td.district_id, td.region, COUNT(DISTINCT fc.client_id) AS female_clients, AVG(fc.birth_date) AS dummy_birth, COUNT(DISTINCT fa.account_id) AS female_accounts, COUNT(DISTINCT fl.loan_id) AS female_loans, AVG(fl.amount) AS avg_loan_amount, SUM(CASE WHEN fl.status = 'C' THEN 1 ELSE 0 END) AS active_loans, SUM(CASE WHEN fl.status = 'A' THEN 1 ELSE 0 END) AS completed_loans, SUM(CASE WHEN fl.status = 'D' THEN 1 ELSE 0 END) AS defaulted_loans FROM top3_districts AS td JOIN female_clients AS fc ON fc.district_id = td.district_id LEFT JOIN female_accounts AS fa ON fa.client_id = fc.client_id LEFT JOIN female_loans AS fl ON fl.account_id = fa.account_id GROUP BY td.district_id, td.region HAVING COUNT(DISTINCT fc.client_id) >= 5 AND COUNT(DISTINCT fl.loan_id) > 0) SELECT COUNT(DISTINCT ds.district_id) AS
-- truncated
```

### bird_0094

- 数据库：financial
- 分类：sql_error
- 细分类：circuit_breaker
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=3;predicted=3'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:c8b9774edfc782a4ff99afbb3633edbdf056eafd57024bacb751f0020b54c30f;2:worker_failed:sha256:c348e066d84d6d01e83a44b1d5f913ed971cf69fbc8cea332d379ef4306d743d;3:no_progress:sha256:c348e066d84d6d01e83a44b1d5f913ed971cf69fbc8cea332d379ef4306d743d']]
- 错误类别：no_progress
- 脱敏错误：SQLite 子进程异常退出
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：None
- 度量覆盖：1.0
- 种子表：['account', 'disp', 'loan', 'order', 'trans', 'card', 'client', 'district']
- 引用表：['account', 'client', 'disp', 'district', 'trans']
- 投影：['account_id', '(SELECT MAX(A11) - MIN(A11) FROM district)']
- 聚合：['max', 'min']
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
SELECT a.account_id AS account_id, (SELECT MAX(A11) - MIN(A11) FROM district) AS "(SELECT MAX(A11) - MIN(A11) FROM district)" FROM client AS c JOIN disp AS d ON d.client_id = c.client_id JOIN account AS a ON a.account_id = d.account_id JOIN district AS di ON di.district_id = a.district_id WHERE c.gender = 'F' ORDER BY c.birth_date ASC, (SELECT AVG(t.amount) FROM trans AS t WHERE t.account_id = a.account_id) ASC LIMIT 1
```

### bird_0096

- 数据库：financial
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'outer:ci.gender、ci.age_group、ci.region | CustomerWeeklyStatements:T2.client_id、T1.account_id、T1.district_id、T1.date | LoanAndTransactionData:cws.client_id'], ['predicted_group_by', 'outer:oi.gender、oi.age_group、oi.region | cards:d.client_id | loans:a.account_id | trans_agg:t.account_id'], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=7;predicted=9'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:empty_result:sha256:76875bf6b5876d91fa5a9493c76acd17ba6c818e2094b43c0b5c1fd72404ad85;2:no_progress:sha256:76875bf6b5876d91fa5a9493c76acd17ba6c818e2094b43c0b5c1fd72404ad85;3:kept_candidate:no_progress']]
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
- 聚合：['count', 'avg']
- 分组：['oi.gender', 'oi.age_group', 'oi.region']
- 电商规则：[]
- 串库表：[]

```sql
WITH weekly_owners AS (SELECT DISTINCT d.client_id, a.account_id FROM account AS a JOIN disp AS d ON d.account_id = a.account_id WHERE a.frequency = 'weekly' AND d.type = 'OWNER'), owner_info AS (SELECT wo.client_id, wo.account_id, c.gender, CASE WHEN CAST((JULIANDAY('2026-10-01') - JULIANDAY(c.birth_date)) / 365.25 AS INTEGER) < 30 THEN 'Young' WHEN CAST((JULIANDAY('2026-10-01') - JULIANDAY(c.birth_date)) / 365.25 AS INTEGER) < 50 THEN 'Middle' ELSE 'Old' END AS age_group, ds.A3 AS region FROM weekly_owners AS wo JOIN client AS c ON c.client_id = wo.client_id JOIN account AS a ON a.account_id = wo.account_id JOIN district AS ds ON ds.district_id = a.district_id), cards AS (SELECT d.client_id, COUNT(cd.card_id) AS n_cards FROM disp AS d JOIN card AS cd ON cd.disp_id = d.disp_id WHERE d.type = 'OWNER' GROUP BY d.client_id), loans AS (SELECT a.account_id, COUNT(l.loan_id) AS n_loans, SUM(l.amount) AS total_loan_amount FROM account AS a JOIN loan AS l ON l.account_id = a.account_id GROUP BY a.account_id), trans_agg AS (SELECT t.account_id, COUNT(t.trans_id) AS n_trans, SUM(t.balance) AS net_balance FROM trans AS t GROUP BY t.account_id) SELECT COUNT(DISTINCT oi.client_id) AS total_weekly_owners, oi.gender AS gender, oi.age_group AS age_group, oi.region AS region, ROUND(AVG(COALESCE(ca.n_cards, 0)), 2) AS avg_cards_per_customer, ROUND(AVG(COALESCE(lo.n_loans, 0)), 2) AS avg_loans_per_customer, ROUND(AVG(lo.total_loan_amount), 2) AS avg_loan_amount, ROUND(AVG(COALESCE(ta.n_trans, 0)), 2) AS avg_transactions, ROUND(AVG(ta.net_balance), 2) AS avg_net_balance, COUNT(DISTINCT CASE WHEN lo.n_loans > 0 THEN oi.client_id END) AS customers_with_loans, ROUND(CAST(COUNT(DISTINCT CASE WHEN lo.n_loans > 0 THEN oi.client_id END) AS REAL) * 100 / COUNT(DISTINCT oi.client_id), 2) AS percent_with_loans FROM owner_info AS oi LEFT JOIN cards AS ca ON ca.client_id = oi.client_id LEFT JOIN loans AS lo ON lo.account_id = oi.account_id LEFT JOIN trans_agg AS ta ON ta.account_id = oi.account_i
-- truncated
```

### bird_0097

- 数据库：financial
- 分类：other_result_mismatch
- 细分类：filter_scope
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'ClientLoanInfo:d.client_id、d.type、a.frequency | ClientTransactions:d.client_id | ClientCards:d.client_id'], ['predicted_group_by', 'loan_agg:l.account_id | trans_agg:t.account_id | card_agg:d.account_id'], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', 'DISPONENT'], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=8;predicted=8'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '']]
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
WITH owner_disp AS (SELECT disp_id, client_id, account_id FROM disp WHERE type = 'OWNER'), eligible_accounts AS (SELECT DISTINCT t.account_id FROM trans AS t WHERE t.date > (SELECT a.date FROM account AS a WHERE a.account_id = t.account_id)), loan_agg AS (SELECT l.account_id, COUNT(*) AS loan_count, AVG(l.amount) AS avg_loan_amount, SUM(CASE WHEN l.status = 'C' THEN 1 ELSE 0 END) AS completed_loans, SUM(CASE WHEN l.status = 'A' THEN 1 ELSE 0 END) AS active_loans FROM loan AS l GROUP BY l.account_id), trans_agg AS (SELECT t.account_id, COUNT(*) AS transaction_count, SUM(CASE WHEN t.type = 'credit' THEN t.amount ELSE 0 END) AS total_income, SUM(CASE WHEN t.type = 'debit' THEN t.amount ELSE 0 END) AS total_expense, SUM(CASE WHEN t.type = 'credit' THEN t.amount ELSE -t.amount END) AS net_balance, MAX(t.date) AS last_transaction_date FROM trans AS t GROUP BY t.account_id), card_agg AS (SELECT d.account_id, COUNT(c.card_id) AS card_count, GROUP_CONCAT(DISTINCT c.type) AS card_types FROM card AS c JOIN disp AS d ON c.disp_id = d.disp_id GROUP BY d.account_id), base AS (SELECT cl.client_id, cl.gender, cl.birth_date, ds.A2 AS district_name, ds.A3 AS region, COALESCE(la.loan_count, 0) AS loan_count, COALESCE(la.avg_loan_amount, 0) AS avg_loan_amount, COALESCE(la.active_loans, 0) AS active_loans, COALESCE(la.completed_loans, 0) AS completed_loans, COALESCE(ta.transaction_count, 0) AS transaction_count, COALESCE(ta.total_income, 0) AS total_income, COALESCE(ta.total_expense, 0) AS total_expense, COALESCE(ta.net_balance, 0) AS net_balance, ta.last_transaction_date, COALESCE(ca.card_count, 0) AS card_count, ca.card_types FROM owner_disp AS od JOIN eligible_accounts AS ea ON od.account_id = ea.account_id JOIN client AS cl ON od.client_id = cl.client_id JOIN account AS a ON od.account_id = a.account_id JOIN district AS ds ON a.district_id = ds.district_id LEFT JOIN loan_agg AS la ON od.account_id = la.account_id LEFT JOIN trans_agg AS ta ON od.account_id = ta.account_id LEFT JOIN c
-- truncated
```

### bird_0100

- 数据库：financial
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', 'loan_agg:b.client_id'], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=4;predicted=5'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '']]
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
- 聚合：['count', 'avg', 'min', 'max']
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH base AS (SELECT c.client_id, c.birth_date, a.account_id, a.date AS account_open_date, CAST(STRFTIME('%Y', a.date) AS INTEGER) AS account_year, (CAST(STRFTIME('%Y', '2026-10-01') AS INTEGER) - CAST(STRFTIME('%Y', c.birth_date) AS INTEGER) - CASE WHEN STRFTIME('%m-%d', '2026-10-01') < STRFTIME('%m-%d', c.birth_date) THEN 1 ELSE 0 END) AS age_at_opening FROM client AS c JOIN disp AS d ON d.client_id = c.client_id AND d.type = 'OWNER' JOIN account AS a ON a.account_id = d.account_id JOIN district AS di ON di.district_id = c.district_id WHERE c.gender = 'F' AND CAST(STRFTIME('%Y', c.birth_date) AS INTEGER) < 1950 AND di.A3 = 'Sokolov'), loan_agg AS (SELECT b.client_id, COUNT(DISTINCT CASE WHEN NOT l.loan_id IS NULL THEN l.loan_id END) AS n_loans, COUNT(DISTINCT CASE WHEN l.status = 'C' THEN l.loan_id END) AS n_good_loans, COUNT(DISTINCT CASE WHEN l.status = 'B' THEN l.loan_id END) AS n_debt_loans FROM base AS b LEFT JOIN loan AS l ON l.account_id = b.account_id GROUP BY b.client_id) SELECT COUNT(DISTINCT b.client_id) AS total_female_clients, AVG(b.age_at_opening) AS avg_age_at_account_opening, COUNT(DISTINCT CASE WHEN la.n_loans > 0 THEN b.client_id END) AS clients_with_loans, COUNT(DISTINCT CASE WHEN la.n_good_loans > 0 THEN b.client_id END) AS clients_with_good_loans, COUNT(DISTINCT CASE WHEN la.n_debt_loans > 0 THEN b.client_id END) AS clients_with_debt, MIN(b.account_year) AS earliest_account_year, MAX(b.account_year) AS latest_account_year FROM base AS b LEFT JOIN loan_agg AS la ON la.client_id = b.client_id
```

### bird_0103

- 数据库：financial
- 分类：other_result_mismatch
- 细分类：join_semantics
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'ClientAccountInfo:c.client_id'], ['predicted_group_by', 'agg:b.client_id、b.gender、b.birth_date、b.card_type、b.age_at_card_issue、b.district_name、b.region'], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=7;predicted=6'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '']]
- 错误类别：None
- 脱敏错误：None
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：None
- 度量覆盖：None
- 种子表：['loan', 'card', 'district', 'client', 'account', 'disp', 'order', 'trans']
- 引用表：['account', 'card', 'client', 'disp', 'district', 'loan', 'trans']
- 投影：['client_id', 'gender', 'birth_date', 'card_type', 'age_at_card_issue', 'account_count', 'loan_count', 'active_loans', 'avg_loan_amount', 'district_name', 'region', 'avg_salary', 'borrower_category', 'age_rank_by_gender']
- 聚合：['rank']
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH base AS (SELECT c.client_id, c.gender, c.birth_date, cd.type AS card_type, CAST((JULIANDAY(cd.issued) - JULIANDAY(c.birth_date)) / 365.25 AS INTEGER) AS age_at_card_issue, a.account_id, d.A3 AS region, d.A2 AS district_name FROM card AS cd JOIN disp AS dp ON cd.disp_id = dp.disp_id JOIN client AS c ON dp.client_id = c.client_id JOIN account AS a ON dp.account_id = a.account_id JOIN district AS d ON a.district_id = d.district_id WHERE cd.issued = '1994-03-03'), agg AS (SELECT b.client_id, b.gender, b.birth_date, b.card_type, b.age_at_card_issue, b.district_name, b.region, COUNT(DISTINCT b.account_id) AS account_count, COUNT(DISTINCT l.loan_id) AS loan_count, COUNT(DISTINCT CASE WHEN l.status = 'C' THEN l.loan_id END) AS active_loans, AVG(l.amount) AS avg_loan_amount, AVG(t.amount) AS avg_salary FROM base AS b LEFT JOIN loan AS l ON b.account_id = l.account_id LEFT JOIN trans AS t ON b.account_id = t.account_id AND t.k_symbol = 'SALARY' GROUP BY b.client_id, b.gender, b.birth_date, b.card_type, b.age_at_card_issue, b.district_name, b.region) SELECT client_id, gender, birth_date, card_type, age_at_card_issue, account_count, loan_count, active_loans, avg_loan_amount, district_name, region, avg_salary, CASE WHEN age_at_card_issue < 30 AND active_loans > 0 THEN 'Young Active Borrower' WHEN age_at_card_issue < 30 THEN 'Young Borrower' WHEN age_at_card_issue < 60 AND active_loans > 0 THEN 'Middle-aged Active Borrower' WHEN age_at_card_issue < 60 THEN 'Middle-aged Borrower' WHEN active_loans > 0 THEN 'Senior Active Borrower' ELSE 'Senior Borrower' END AS borrower_category, RANK() OVER (PARTITION BY gender ORDER BY age_at_card_issue DESC) AS age_rank_by_gender FROM agg ORDER BY gender, age_rank_by_gender
```

### bird_0105

- 数据库：financial
- 分类：other_result_mismatch
- 细分类：response_shape
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'ClientsInDistrict:d.district_id'], ['predicted_group_by', 'client_agg:c.district_id | trans_agg:t.account_id'], ['aggregation_only_in_cte', 'client_agg,trans_agg'], ['missing_output_labels', 'PRIJEM'], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=5;predicted=5'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:missing_entity:sha256:656b89ee9d292924f320ba6dee264786fe7ed24e9743c503b8134278edbcbefc;2:database_error:sha256:7b674721b13689de3f66160312cb8920e2c964e80f85e73bbd380eff4e1927d6;3:accepted:']]
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
WITH loan_info AS (SELECT account_id, date AS loan_date FROM loan WHERE date = '1994-08-25'), acct AS (SELECT a.account_id, a.district_id, a.date AS account_open_date, CAST(JULIANDAY(li.loan_date) - JULIANDAY(a.date) AS INTEGER) AS days_account_open_before_loan, li.loan_date AS loan_date FROM account AS a JOIN loan_info AS li ON li.account_id = a.account_id), client_agg AS (SELECT c.district_id, COUNT(DISTINCT c.client_id) AS num_clients, SUM(CASE WHEN c.gender = 'M' THEN 1 ELSE 0 END) AS male_clients, SUM(CASE WHEN c.gender = 'F' THEN 1 ELSE 0 END) AS female_clients, AVG(CAST((JULIANDAY('2026-10-01') - JULIANDAY(c.birth_date)) / 365.25 AS REAL)) AS avg_client_age FROM client AS c GROUP BY c.district_id), trans_agg AS (SELECT t.account_id, COUNT(*) AS transactions_before_loan, SUM(t.amount) AS total_income_before_loan FROM trans AS t JOIN acct AS a ON a.account_id = t.account_id WHERE t.date < a.loan_date GROUP BY t.account_id) SELECT acct.district_id AS district_id, district.A2 AS district_name, district.A3 AS region, acct.account_open_date AS account_open_date, acct.days_account_open_before_loan AS days_account_open_before_loan, district.A11 AS avg_salary, district.A12 AS unemployment_rate_1995, district.A13 AS salary_rank, district.A14 AS unemployment_rank, client_agg.num_clients AS num_clients, client_agg.male_clients AS male_clients, client_agg.female_clients AS female_clients, client_agg.avg_client_age AS avg_client_age, trans_agg.transactions_before_loan AS transactions_before_loan, trans_agg.total_income_before_loan AS total_income_before_loan FROM acct JOIN district ON district.district_id = acct.district_id LEFT JOIN client_agg ON client_agg.district_id = acct.district_id LEFT JOIN trans_agg ON trans_agg.account_id = acct.account_id
```

### bird_0106

- 数据库：financial
- 分类：other_result_mismatch
- 细分类：grouping_grain
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=8;predicted=9'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:join_not_on_graph:sha256:9c7e445cf7388e0f3906371d62694dc11afba740a87631d4556201564033b099;2:accepted:']]
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
WITH target_client AS (SELECT c.client_id, c.gender, c.birth_date, c.district_id, d.disp_id, d.account_id FROM card AS ca JOIN disp AS d ON ca.disp_id = d.disp_id JOIN client AS c ON d.client_id = c.client_id WHERE ca.issued = '1996-10-21'), largest_trans AS (SELECT t.trans_id, t.account_id, t.date, t.type, t.amount, t.balance, t.k_symbol FROM trans AS t JOIN target_client AS tc ON t.account_id = tc.account_id ORDER BY t.amount DESC LIMIT 1) SELECT tc.client_id AS client_id, ca.card_id AS card_id, ca.type AS card_type, tc.gender AS gender, CAST((JULIANDAY('2026-10-01') - JULIANDAY(tc.birth_date)) / 365.25 AS INTEGER) AS client_age, dist.A2 AS district_name, dist.A3 AS region, lt.trans_id AS trans_id, lt.amount AS largest_transaction_amount, lt.type AS transaction_type, lt.date AS transaction_date, lt.balance AS balance_after_transaction, lt.k_symbol AS transaction_category, l.status AS loan_status, l.amount AS loan_amount, o.order_id AS order_id, o.bank_to AS bank_to FROM target_client AS tc JOIN card AS ca ON ca.disp_id = tc.disp_id JOIN account AS a ON a.account_id = tc.account_id JOIN district AS dist ON a.district_id = dist.district_id JOIN largest_trans AS lt ON lt.account_id = tc.account_id LEFT JOIN loan AS l ON l.account_id = tc.account_id LEFT JOIN "order" AS o ON o.account_id = tc.account_id LIMIT 1
```

### bird_0111

- 数据库：financial
- 分类：other_result_mismatch
- 细分类：grouping_grain
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'ClientInfo:d.account_id | AccountActivity:account_id | LoanStatus:account_id'], ['predicted_group_by', ''], ['aggregation_only_in_cte', 'acct_stats,client_stats,trans_stats,loan_stats,q_stats'], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=5;predicted=9'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:cartesian_product:sha256:29ee50ff2b12c7713a195bd2c2424b1a70306ac27beeade798536885f60c1884;2:join_not_on_graph:sha256:9c1c6b9a61ef1c01679f803e71cc7fff6d82c312ea1c8a624c3dd775f51ed180;3:kept_candidate:join_not_on_graph']]
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
- 聚合：[]
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH acct AS (SELECT a.account_id, a.date FROM account AS a JOIN district AS d ON a.district_id = d.district_id WHERE d.A3 = 'Litomerice' AND STRFTIME('%Y', a.date) = '1996'), owner_clients AS (SELECT ac.account_id, c.client_id, c.gender, c.birth_date FROM acct AS ac JOIN disp AS dp ON dp.account_id = ac.account_id AND dp.type = 'OWNER' JOIN client AS c ON c.client_id = dp.client_id), acct_stats AS (SELECT COUNT(DISTINCT account_id) AS total_accounts, COUNT(DISTINCT CASE WHEN cnt > 1 THEN account_id END) AS accounts_with_multiple_clients FROM (SELECT account_id, COUNT(*) AS cnt FROM owner_clients GROUP BY account_id)), client_stats AS (SELECT AVG((JULIANDAY('2026-10-01') - JULIANDAY(birth_date)) / 365.25) AS average_client_age, SUM(CASE WHEN gender = 'M' THEN 1 ELSE 0 END) AS total_male_clients, SUM(CASE WHEN gender = 'F' THEN 1 ELSE 0 END) AS total_female_clients FROM owner_clients), trans_stats AS (SELECT COUNT(t.trans_id) AS total_transactions_in_1996, SUM(CASE WHEN t.type = 'credit' THEN t.amount ELSE 0 END) AS total_deposits_in_1996 FROM acct AS ac JOIN trans AS t ON t.account_id = ac.account_id WHERE STRFTIME('%Y', t.date) = '1996'), loan_stats AS (SELECT COUNT(l.loan_id) AS total_loans, AVG(l.amount) AS avg_loan_amount, COUNT(DISTINCT l.account_id) AS accounts_with_loans FROM acct AS ac JOIN loan AS l ON l.account_id = ac.account_id), q_stats AS (SELECT SUM(CASE WHEN CAST(STRFTIME('%m', date) AS INTEGER) BETWEEN 1 AND 3 THEN 1 ELSE 0 END) AS q1, SUM(CASE WHEN CAST(STRFTIME('%m', date) AS INTEGER) BETWEEN 4 AND 6 THEN 1 ELSE 0 END) AS q2, SUM(CASE WHEN CAST(STRFTIME('%m', date) AS INTEGER) BETWEEN 7 AND 9 THEN 1 ELSE 0 END) AS q3, SUM(CASE WHEN CAST(STRFTIME('%m', date) AS INTEGER) BETWEEN 10 AND 12 THEN 1 ELSE 0 END) AS q4, COUNT(*) AS total FROM acct) SELECT acct_stats.total_accounts AS total_accounts, acct_stats.accounts_with_multiple_clients AS accounts_with_multiple_clients, client_stats.average_client_age AS average_client_age, client_stats.total_male_cl
-- truncated
```

### bird_0112

- 数据库：financial
- 分类：other_result_mismatch
- 细分类：join_semantics
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'account_transactions:ca.client_id、ca.account_id、ca.account_district'], ['predicted_group_by', 'trans_agg:t.account_id | loan_agg:l.account_id | card_agg:d.account_id'], ['aggregation_only_in_cte', 'trans_agg,loan_agg,card_agg'], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=8;predicted=9'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '']]
- 错误类别：None
- 脱敏错误：None
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：None
- 度量覆盖：None
- 种子表：['client', 'disp', 'trans', 'account', 'card', 'district', 'loan', 'order']
- 引用表：['account', 'card', 'client', 'disp', 'district', 'loan', 'trans']
- 投影：['residence_district', 'account_district', 'district_comparison', 'account_open_date', 'transaction_count', 'total_income', 'total_expense', 'max_balance', 'loan_count', 'card_count', 'region', 'urban_ratio', 'avg_salary', 'entrepreneurs_per_1000']
- 聚合：[]
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH target_client AS (SELECT client_id, district_id FROM client WHERE gender = 'F' AND birth_date = '1976-01-29'), owned_accounts AS (SELECT DISTINCT a.account_id, a.district_id, a.date AS account_open_date FROM account AS a JOIN disp AS d ON d.account_id = a.account_id JOIN target_client AS tc ON tc.client_id = d.client_id WHERE d.type = 'OWNER'), trans_agg AS (SELECT t.account_id, COUNT(*) AS transaction_count, SUM(CASE WHEN t.type = 'credit' THEN t.amount ELSE 0 END) AS total_income, SUM(CASE WHEN t.type = 'debit' THEN t.amount ELSE 0 END) AS total_expense, MAX(t.balance) AS max_balance FROM trans AS t JOIN owned_accounts AS oa ON oa.account_id = t.account_id GROUP BY t.account_id), loan_agg AS (SELECT l.account_id, COUNT(*) AS loan_count FROM loan AS l JOIN owned_accounts AS oa ON oa.account_id = l.account_id GROUP BY l.account_id), card_agg AS (SELECT d.account_id, COUNT(*) AS card_count FROM card AS c JOIN disp AS d ON d.disp_id = c.disp_id JOIN owned_accounts AS oa ON oa.account_id = d.account_id GROUP BY d.account_id) SELECT (SELECT A3 FROM district WHERE district_id = (SELECT district_id FROM target_client)) AS residence_district, (SELECT A3 FROM district WHERE district_id = oa.district_id) AS account_district, CASE WHEN oa.district_id = (SELECT district_id FROM target_client) THEN 'Same District' ELSE 'Different District' END AS district_comparison, oa.account_open_date AS account_open_date, COALESCE(ta.transaction_count, 0) AS transaction_count, COALESCE(ta.total_income, 0) AS total_income, COALESCE(ta.total_expense, 0) AS total_expense, COALESCE(ta.max_balance, 0) AS max_balance, COALESCE(la.loan_count, 0) AS loan_count, COALESCE(ca.card_count, 0) AS card_count, (SELECT A3 FROM district WHERE district_id = oa.district_id) AS region, (SELECT CAST(A10 AS REAL) FROM district WHERE district_id = oa.district_id) AS urban_ratio, (SELECT CAST(A11 AS REAL) FROM district WHERE district_id = oa.district_id) AS avg_salary, (SELECT CAST(A14 AS REAL) FROM district W
-- truncated
```

### bird_0113

- 数据库：financial
- 分类：other_result_mismatch
- 细分类：missing_required_table
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'ClientTransactions:LC.client_id、LC.birth_date、LC.age_at_loan、d.A2、d.A3 | CardInfo:LC.client_id'], ['predicted_group_by', 'trans_agg:t.account_id | card_agg:d.account_id | prev_loans:l.account_id'], ['aggregation_only_in_cte', 'trans_agg,card_agg,prev_loans'], ['missing_output_labels', 'None'], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=11;predicted=11'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:join_not_on_graph:sha256:aa78f5b977574c4b4bc27c59f47673fce7db7b0cd1b48afbe349d2ed382a4914;2:accepted:']]
- 错误类别：None
- 脱敏错误：None
- 上下文召回：1.0
- 引用表召回：0.8571428571428571
- 维度覆盖：None
- 实体覆盖：None
- 度量覆盖：1.0
- 种子表：['card', 'client', 'loan', 'trans', 'disp', 'account', 'district', 'order']
- 引用表：['card', 'client', 'disp', 'district', 'loan', 'trans']
- 投影：['birth_date', 'age_at_loan', 'district_name', 'region', 'transaction_count', 'total_income', 'total_expense', 'expense_to_income_ratio', 'max_balance', 'min_balance', 'card_count', 'card_types', 'previous_loans']
- 聚合：[]
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH target_loan AS (SELECT l.loan_id, l.account_id, l.date AS loan_date, l.amount FROM loan AS l WHERE l.amount = 98832 AND STRFTIME('%Y', l.date) = '1996' AND STRFTIME('%m-%d', l.date) = '01-03'), client_info AS (SELECT c.client_id, c.birth_date, c.district_id, CAST((JULIANDAY(tl.loan_date) - JULIANDAY(c.birth_date)) / 365.25 AS INTEGER) AS age_at_loan FROM target_loan AS tl JOIN disp AS d ON d.account_id = tl.account_id JOIN client AS c ON c.client_id = d.client_id), trans_agg AS (SELECT t.account_id, COUNT(*) AS transaction_count, SUM(CASE WHEN t.amount > 0 THEN t.amount ELSE 0 END) AS total_income, SUM(CASE WHEN t.amount < 0 THEN -t.amount ELSE 0 END) AS total_expense, MAX(t.balance) AS max_balance, MIN(t.balance) AS min_balance FROM trans AS t JOIN target_loan AS tl ON tl.account_id = t.account_id WHERE t.date < tl.loan_date GROUP BY t.account_id), card_agg AS (SELECT d.account_id, COUNT(c.card_id) AS card_count, GROUP_CONCAT(DISTINCT c.type) AS card_types FROM card AS c JOIN disp AS d ON d.disp_id = c.disp_id JOIN target_loan AS tl ON tl.account_id = d.account_id GROUP BY d.account_id), prev_loans AS (SELECT l.account_id, COUNT(*) AS previous_loans FROM loan AS l JOIN target_loan AS tl ON tl.account_id = l.account_id WHERE l.date < tl.loan_date GROUP BY l.account_id) SELECT ci.birth_date AS birth_date, ci.age_at_loan AS age_at_loan, dist.A2 AS district_name, dist.A3 AS region, ta.transaction_count AS transaction_count, ta.total_income AS total_income, ta.total_expense AS total_expense, ROUND(CAST(ta.total_expense AS REAL) / NULLIF(ta.total_income, 0), 4) AS expense_to_income_ratio, ta.max_balance AS max_balance, ta.min_balance AS min_balance, ca.card_count AS card_count, ca.card_types AS card_types, COALESCE(pl.previous_loans, 0) AS previous_loans FROM target_loan AS tl JOIN disp AS d ON d.account_id = tl.account_id JOIN client_info AS ci ON ci.client_id = d.client_id JOIN district AS dist ON dist.district_id = ci.district_id LEFT JOIN trans_agg AS ta ON ta.a
-- truncated
```

### bird_0115

- 数据库：financial
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'RegionStats:d.district_id、d.A3、d.A4'], ['predicted_group_by', 'outer:mp.district_id、mp.district_name、mp.region、mp.inhabitants'], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=1'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '']]
- 错误类别：None
- 脱敏错误：None
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：None
- 度量覆盖：1.0
- 种子表：['district', 'account', 'client', 'card', 'disp', 'loan', 'order', 'trans']
- 引用表：['client', 'district']
- 投影：['district_id', 'district_name', 'region', 'inhabitants', 'total_clients', 'male_clients', 'pct_male']
- 聚合：['count', 'sum']
- 分组：['mp.district_id', 'mp.district_name', 'mp.region', 'mp.inhabitants']
- 电商规则：[]
- 串库表：[]

```sql
WITH south_bohemia AS (SELECT district_id, A2 AS district_name, A3 AS region, A4 AS inhabitants FROM district WHERE A3 = 'south Bohemia'), most_populated AS (SELECT district_id, district_name, region, inhabitants FROM south_bohemia ORDER BY inhabitants DESC LIMIT 1) SELECT mp.district_id AS district_id, mp.district_name AS district_name, mp.region AS region, mp.inhabitants AS inhabitants, COUNT(c.client_id) AS total_clients, SUM(CASE WHEN c.gender = 'M' THEN 1 ELSE 0 END) AS male_clients, ROUND(CAST(SUM(CASE WHEN c.gender = 'M' THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(c.client_id), 2) AS pct_male FROM most_populated AS mp JOIN client AS c ON c.district_id = mp.district_id GROUP BY mp.district_id, mp.district_name, mp.region, mp.inhabitants
```

### bird_0117

- 数据库：financial
- 分类：other_result_mismatch
- 细分类：join_semantics
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'RegionSummary:region'], ['predicted_group_by', 'agg:region'], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=4;predicted=4'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '']]
- 错误类别：None
- 脱敏错误：None
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：None
- 度量覆盖：1.0
- 种子表：['loan', 'order', 'trans', 'account', 'card', 'client', 'disp', 'district']
- 引用表：['account', 'client', 'disp', 'district', 'loan']
- 投影：['region', 'paid_amount_percentage', 'successful_loans_percentage', 'successful_loans', 'total_loans', 'paid_amount', 'total_amount', 'avg_interest_paid_successful', 'avg_interest_paid_all', 'overall_percentage']
- 聚合：['sum']
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH loan_region AS (SELECT d.A3 AS region, l.loan_id, l.amount, l.payments, l.status FROM loan AS l JOIN account AS a ON l.account_id = a.account_id JOIN district AS d ON a.district_id = d.district_id JOIN disp AS dp ON dp.account_id = a.account_id JOIN client AS c ON dp.client_id = c.client_id WHERE dp.type = 'OWNER'), agg AS (SELECT region, SUM(CASE WHEN status = 'C' THEN amount ELSE 0 END) AS paid_amount, SUM(amount) AS total_amount, SUM(CASE WHEN status = 'C' THEN 1 ELSE 0 END) AS successful_loans, COUNT(*) AS total_loans, AVG(CASE WHEN status = 'C' THEN payments END) AS avg_interest_paid_successful, AVG(payments) AS avg_interest_paid_all FROM loan_region GROUP BY region) SELECT region, ROUND(CAST(paid_amount AS REAL) * 100 / NULLIF(total_amount, 0), 2) AS paid_amount_percentage, ROUND(CAST(successful_loans AS REAL) * 100 / NULLIF(total_loans, 0), 2) AS successful_loans_percentage, successful_loans, total_loans, paid_amount, total_amount, avg_interest_paid_successful, avg_interest_paid_all, ROUND(CAST(SUM(paid_amount) OVER () AS REAL) * 100 / NULLIF(SUM(total_amount) OVER (), 0), 2) AS overall_percentage FROM agg ORDER BY region
```

### bird_0119

- 数据库：financial
- 分类：sql_error
- 细分类：circuit_breaker
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'AccountStats:a.account_id | ClientDetails:a.account_id | LoanInfo:a.account_id'], ['predicted_group_by', 'trans_agg:t.account_id | client_agg:d.account_id | loan_agg:l.account_id'], ['aggregation_only_in_cte', 'trans_agg,client_agg,loan_agg'], ['missing_output_labels', 'Rural'], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=8;predicted=8'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:e5c89e44be1ce602447a5b1b4bf7d9600a29b6629c034b76ede07a963cef96fd;2:no_progress:sha256:e5c89e44be1ce602447a5b1b4bf7d9600a29b6629c034b76ede07a963cef96fd']]
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
WITH
  base_accounts AS (
    SELECT a.account_id, a.district_id
    FROM account a
    WHERE strftime('%Y', a.date) = '1993'
  ),
  trans_agg AS (
    SELECT t.account_id,
           COUNT(*) AS transaction_count,
           SUM(CASE WHEN t.type = 'credit' THEN t.amount ELSE -t.amount END) AS net_cash_flow,
           AVG(t.balance) AS balance_volatility
    FROM trans t
    JOIN base_accounts ba ON t.account_id = ba.account_id
    GROUP BY t.account_id
  ),
  client_agg AS (
    SELECT d.account_id,
           COUNT(DISTINCT c.client_id) AS client_count,
           MAX(CASE WHEN d.type = 'OWNER' THEN c.gender END) AS owner_gender,
           AVG(CAST((julianday('2026-10-01') - julianday(c.birth_date)) / 365.25 AS REAL)) AS avg_client_age
    FROM disp d
    JOIN client c ON d.client_id = c.client_id
    JOIN base_accounts ba ON d.account_id = ba.account_id
    GROUP BY d.account_id
  ),
  loan_agg AS (
    SELECT l.account_id,
           COUNT(*) AS loan_count,
           SUM(l.amount) AS total_loan_amount,
           AVG(l.duration) AS avg_loan_duration_months,
           SUM(CASE WHEN l.status = 'C' THEN 1 ELSE 0 END) AS running_loans,
           SUM(CASE WHEN l.status = 'A' THEN 1 ELSE 0 END) AS finished_loans,
           SUM(CASE WHEN l.status = 'B' THEN 1 ELSE 0 END) AS defaulted_loans
    FROM loan l
    JOIN base_accounts ba ON l.account_id = ba.account_id
    GROUP BY l.account_id
  )
SELECT
  ba.account_id AS account_id,
  di.A2 AS district_name,
  di.A3 AS district_region,
  di.A4 AS urbanization_category,
  COALESCE(ta.transaction_count, 0) AS transaction_count,
  COALESCE(ta.net_cash_flow, 0) AS net_cash_flow,
  COALESCE(ta.balance_volatility, 0) AS balance_volatility,
  COALESCE(ca.client_count, 0) AS client_count,
  ca.owner_gender AS owner_gender,
  ca.avg_client_age AS avg_client_age,
  COALESCE(la.loan_count, 0) AS loan_count,
  COALESCE(la.total_loan_amount, 0) AS total_loan_amount,
  la.avg_loan_duration_months AS avg_loan_duration_months,
  COA
-- truncated
```

### bird_0121

- 数据库：financial
- 分类：other_result_mismatch
- 细分类：filter_scope
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'TransactionStats:t.account_id | LoanInfo:l.account_id'], ['predicted_group_by', 'base:a.account_id、a.date、d.A2、d.A3、c.gender、c.birth_date'], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', 'OWNER'], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=8;predicted=5'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:empty_result:sha256:76875bf6b5876d91fa5a9493c76acd17ba6c818e2094b43c0b5c1fd72404ad85;2:accepted:']]
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
- 聚合：['rank']
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH base AS (SELECT a.account_id, a.date AS opening_date, d.A2 AS district_name, d.A3 AS region, c.gender, CAST((JULIANDAY('2026-10-01') - JULIANDAY(c.birth_date)) / 365.25 AS INTEGER) AS client_age, COUNT(t.trans_id) AS transaction_count, COALESCE(SUM(CASE WHEN t.amount > 0 THEN t.amount ELSE 0 END), 0) AS total_income, COALESCE(SUM(CASE WHEN t.amount < 0 THEN -t.amount ELSE 0 END), 0) AS total_expense, COALESCE(SUM(t.amount), 0) AS net_balance, COALESCE(MAX(t.balance), 0) AS max_balance, COUNT(DISTINCT l.loan_id) AS loan_count, COALESCE(SUM(l.amount), 0) AS total_loan_amount, MAX(l.status) AS loan_status FROM account AS a JOIN district AS d ON a.district_id = d.district_id JOIN disp AS dp ON dp.account_id = a.account_id JOIN client AS c ON dp.client_id = c.client_id LEFT JOIN trans AS t ON t.account_id = a.account_id LEFT JOIN loan AS l ON l.account_id = a.account_id WHERE d.A2 = 'Prachatice' GROUP BY a.account_id, a.date, d.A2, d.A3, c.gender, c.birth_date) SELECT account_id, opening_date, district_name, region, gender, client_age, transaction_count, total_income, total_expense, net_balance, max_balance, loan_count, total_loan_amount, loan_status, CASE WHEN net_balance > 100000 THEN 'High Value' WHEN net_balance > 50000 THEN 'Medium Value' ELSE 'Low Value' END AS customer_category, RANK() OVER (ORDER BY net_balance DESC) AS balance_rank FROM base ORDER BY net_balance DESC
```

### bird_0122

- 数据库：financial
- 分类：other_result_mismatch
- 细分类：join_semantics
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'DistrictStats:d.district_id、d.A2、d.A3、d.A11、d.A12'], ['predicted_group_by', 'district_stats:a.district_id | trans_count:a.account_id'], ['aggregation_only_in_cte', 'district_stats,loan_rank,trans_count'], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=8;predicted=8'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '']]
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
- 聚合：[]
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH loan_base AS (SELECT l.loan_id, l.account_id, l.amount AS loan_amount, l.duration AS loan_duration_months, l.status, d.district_id, d.A2 AS district_name, d.A3 AS region, c.gender, c.birth_date, d.A11 AS district_avg_salary, d.A12 AS unemployment_rate_1995 FROM loan AS l JOIN account AS a ON l.account_id = a.account_id JOIN disp AS dp ON a.account_id = dp.account_id JOIN client AS c ON dp.client_id = c.client_id JOIN district AS d ON a.district_id = d.district_id WHERE l.loan_id = 4990), district_stats AS (SELECT a.district_id, COUNT(l.loan_id) AS district_total_loans, AVG(l.amount) AS district_avg_loan_amount, SUM(CASE WHEN l.status = 'C' THEN 0 ELSE 1 END) AS district_problematic_loans FROM loan AS l JOIN account AS a ON l.account_id = a.account_id GROUP BY a.district_id), loan_rank AS (SELECT l.loan_id, a.district_id, RANK() OVER (PARTITION BY a.district_id ORDER BY l.amount DESC) AS district_loan_rank FROM loan AS l JOIN account AS a ON l.account_id = a.account_id), trans_count AS (SELECT a.account_id, COUNT(t.trans_id) AS total_transactions FROM account AS a JOIN trans AS t ON t.account_id = a.account_id GROUP BY a.account_id) SELECT lb.loan_id AS loan_id, lb.district_name AS district_name, lb.region AS region, lb.gender AS gender, lb.birth_date AS birth_date, lb.loan_amount AS loan_amount, lb.loan_duration_months AS loan_duration_months, CASE lb.status WHEN 'A' THEN 'Contract finished, no problems' WHEN 'B' THEN 'Contract finished, loan not paid' WHEN 'C' THEN 'Running contract, OK so far' WHEN 'D' THEN 'Running contract, client in debt' ELSE 'Unknown' END AS status_description, lb.district_avg_salary AS district_avg_salary, lb.unemployment_rate_1995 AS unemployment_rate_1995, ds.district_total_loans AS district_total_loans, ds.district_avg_loan_amount AS district_avg_loan_amount, ds.district_problematic_loans AS district_problematic_loans, lr.district_loan_rank AS district_loan_rank, tc.total_transactions AS total_transactions FROM loan_base AS lb JOIN d
-- truncated
```

### bird_0123

- 数据库：financial
- 分类：other_result_mismatch
- 细分类：join_semantics
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'LoanStatistics:account_id | TransactionSummary:account_id'], ['predicted_group_by', 'loan_stats:l.account_id | trans_stats:t.account_id'], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=5;predicted=5'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:empty_result:sha256:76875bf6b5876d91fa5a9493c76acd17ba6c818e2094b43c0b5c1fd72404ad85;2:no_progress:sha256:76875bf6b5876d91fa5a9493c76acd17ba6c818e2094b43c0b5c1fd72404ad85;3:kept_candidate:no_progress']]
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
WITH national_avg /* 1. 全国平均工资（district.A11 为平均工资） */ AS (SELECT AVG(A11) AS avg_salary FROM district), loan_stats /* 2. 各账户的贷款统计 */ AS (SELECT l.account_id, MAX(l.amount) AS max_loan_amount, AVG(l.amount) AS avg_loan_amount, COUNT(l.loan_id) AS loan_count FROM loan AS l GROUP BY l.account_id), trans_stats /* 3. 各账户的交易统计 */ AS (SELECT t.account_id, COUNT(t.trans_id) AS transaction_count, SUM(CASE WHEN t.type = 'credit' THEN t.amount ELSE 0 END) AS total_credit, SUM(CASE WHEN t.type = 'debit' THEN t.amount ELSE 0 END) AS total_debit FROM trans AS t GROUP BY t.account_id), owner_info /* 4. 账户持有人（OWNER） */ AS (SELECT d.account_id, c.gender, CAST((JULIANDAY('2026-10-01') - JULIANDAY(c.birth_date)) / 365.25 AS INTEGER) AS age FROM disp AS d JOIN client AS c ON c.client_id = d.client_id WHERE d.type = 'OWNER'), base /* 5. 基础明细 */ AS (SELECT a.account_id, ds.A3 AS district_name, ds.A3 AS region_name, ls.max_loan_amount, ls.avg_loan_amount, ls.loan_count, oi.gender, oi.age, CASE WHEN ts.total_credit IS NULL AND ts.total_debit IS NULL THEN 'No Transactions' WHEN (COALESCE(ts.total_credit, 0) - COALESCE(ts.total_debit, 0)) > 0 THEN 'Positive' ELSE 'Non-Positive' END AS income_category, COALESCE(ts.transaction_count, 0) AS transaction_count, CASE WHEN ts.total_credit IS NULL OR ts.total_credit = 0 THEN NULL ELSE ROUND(COALESCE(ts.total_debit, 0) * 1.0 / ts.total_credit, 4) END AS savings_ratio FROM account AS a JOIN district AS ds ON ds.district_id = a.district_id JOIN loan_stats AS ls ON ls.account_id = a.account_id JOIN owner_info AS oi ON oi.account_id = a.account_id LEFT JOIN trans_stats AS ts ON ts.account_id = a.account_id WHERE ls.max_loan_amount > 300000 AND ds.A11 > (SELECT avg_salary FROM national_avg) AND ((COALESCE(ts.total_credit, 0) - COALESCE(ts.total_debit, 0)) > 0 OR ts.transaction_count IS NULL)) SELECT account_id, district_name, region_name, max_loan_amount, avg_loan_amount, loan_count, gender, age, income_category, transaction_count, savings_ratio, RANK() O
-- truncated
```
