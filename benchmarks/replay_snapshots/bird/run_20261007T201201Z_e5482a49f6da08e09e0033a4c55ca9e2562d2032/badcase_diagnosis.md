# 外部问数诊断

- 来源：bird
- 模型：deepseek-chat
- Prompt：text-to-sql-generic-v59
- 执行准确率：0.48
- 匹配：24
- SQL 错误：10
- 可执行率：0.8
- 方言错误率：0.0
- 上下文召回：1.0
- 引用表召回：0.9933333333333333
- 维度覆盖：1.0
- 实体覆盖：1.0
- 度量覆盖：0.972972972972973
- 结果不一致：16
- 电商规则命中用例：0
- 串库用例：0
- 这是注册库上的模型执行，不是 Gold-only，也不是官方 TPC-DS 分数。

## 未匹配

### bird_0008

- 数据库：california_schools
- 分类：sql_error
- 细分类：circuit_breaker
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', 'base'], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:9505b4f3fe0521a60cfb0d2ecb8211c09940b3aff8214c0dfe3d39cc7a984df6;2:no_progress:sha256:9505b4f3fe0521a60cfb0d2ecb8211c09940b3aff8214c0dfe3d39cc7a984df6']]
- 错误类别：no_progress
- 脱敏错误：修复没有改变症状，已标记 no_progress 并熔断
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
    CASE frpm."Charter School (Y/N)"
      WHEN 1 THEN 'Charter School'
      WHEN 0 THEN 'Non-Charter School'
      ELSE 'Unknown'
    END AS school_type,
    schools.GSoffered AS grade_level,
    frpm."FRPM Count (K-12)" AS frpm_count,
    frpm."Enrollment (K-12)" AS enrollment,
    ROUND(frpm."Percent (%) Eligible FRPM (K-12)" * 100, 2) AS percent_eligible_frpm,
    satscores.NumTstTakr AS num_sat_takers,
    ROUND(satscores.NumTstTakr * 100.0 / NULLIF(satscores.enroll12, 0), 2) AS percent_taking_sat,
    satscores.AvgScrRead AS avg_reading,
    satscores.AvgScrMath AS avg_math,
    satscores.AvgScrWrite AS avg_writing,
    (satscores.AvgScrRead + satscores.AvgScrMath + satscores.AvgScrWrite) AS total_avg_score,
    ROUND(satscores.NumGE1500 * 100.0 / NULLIF(satscores.NumTstTakr, 0), 2) AS percent_scoring_over_1500,
    RANK() OVER (ORDER BY frpm."FRPM Count (K-12)" DESC) AS frpm_rank
  FROM frpm
  JOIN schools ON frpm.CDSCode = schools.CDSCode
  LEFT JOIN satscores ON satscores.cds = schools.CDSCode AND satscores.rtype = 'S'
  WHERE frpm."Enrollment (K-12)" > 0
)
SELECT
  "County",
  "District",
  "School",
  school_type,
  grade_level,
  frpm_count,
  enrollment,
  percent_eligible_frpm,
  num_sat_takers,
  percent_taking_sat,
  avg_reading,
  avg_math,
  avg_writing,
  total_avg_score,
  percent_scoring_over_1500,
  frpm_rank
FROM base
WHERE frpm_rank <= 10
ORDER BY frpm_rank;
```

### bird_0010

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', 'SchoolRankings'], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:142b5aa2209d7fb404994bc8528a470aef2717392dbca5e244ceca570dc117e4;2:accepted:']]
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
WITH SchoolRankings AS (SELECT s.cds, s.sname, s.NumTstTakr, s.AvgScrRead, s.AvgScrMath, s.AvgScrWrite, s.NumGE1500, RANK() OVER (ORDER BY s.AvgScrRead DESC) AS ReadingRank FROM satscores AS s WHERE s.NumTstTakr > 10) SELECT sc.School AS SchoolName, sc.County AS County, sc.City AS City, sc.GSoffered AS GradeSpan, sr.AvgScrRead AS ReadingScore, sr.AvgScrMath AS MathScore, sr.AvgScrWrite AS WritingScore, (sr.AvgScrRead + sr.AvgScrMath + sr.AvgScrWrite) AS TotalSATScore, sr.ReadingRank AS ReadingRank, f."FRPM Count (Ages 5-17)" AS FRPMCount, f."Percent (%) Eligible FRPM (Ages 5-17)" AS FRPMPercentage, f."Enrollment (Ages 5-17)" AS Enrollment, (sr.NumGE1500 * 100.0 / sr.NumTstTakr) AS PercentScoring1500Plus, CASE WHEN sc.Charter = 1 THEN 'Charter School' ELSE 'Non-Charter School' END AS SchoolType, CASE WHEN f."Percent (%) Eligible FRPM (Ages 5-17)" > 75 THEN 'High Poverty (>75%)' WHEN f."Percent (%) Eligible FRPM (Ages 5-17)" > 50 THEN 'Moderate Poverty (50%-75%)' WHEN f."Percent (%) Eligible FRPM (Ages 5-17)" > 25 THEN 'Low Poverty (25%-50%)' ELSE 'Very Low Poverty (<=25%)' END AS PovertyLevel FROM SchoolRankings AS sr JOIN schools AS sc ON sc.CDSCode = sr.cds JOIN frpm AS f ON f.CDSCode = sc.CDSCode WHERE sr.ReadingRank = 1 ORDER BY sr.ReadingRank
```

### bird_0011

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:3be1245e17e635ccb399220b392a12c0357ba5a64f6874edbbe7e5165a0b3a75;2:projection_mismatch:sha256:d466d03b232f49dc80e5b5e7a542ae8d4352396755c0b59bbb3f8203018e95f7;3:projection_mismatch:sha256:3be1245e17e635ccb399220b392a12c0357ba5a64f6874edbbe7e5165a0b3a75;4:projection_mismatch:sha256:d466d03b232f49dc80e5b5e7a542ae8d4352396755c0b59bbb3f8203018e95f7;5:projection_mismatch:sha256:3be1245e17e635ccb399220b392a12c0357ba5a64f6874edbbe7e5165a0b3a75']]
- 错误类别：projection_mismatch
- 脱敏错误：projection_mismatch: charter school 语义优先 schools.Charter（Charter School/Regular School），不要用 frpm.`Charter School (Y/N)` Yes/No；projection_mismatch: enrollment>500：HighEnrollmentSchools + SchoolsWithSATScores 两 CTE；projection_mismatch: 维度“county”有聚合时必须进入 GROUP BY；projection_mismatch: charter school 语义优先使用 schools 表的 Charter 字段，不要用 frpm 的 Y/N 列
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
    CASE frpm."Charter School (Y/N)"
      WHEN 1 THEN 'Yes'
      WHEN 0 THEN 'No'
      ELSE 'Unknown'
    END AS IsCharterSchool,
    satscores.NumTstTakr AS SATTestTakers,
    (COALESCE(satscores.AvgScrRead,0) + COALESCE(satscores.AvgScrMath,0) + COALESCE(satscores.AvgScrWrite,0)) AS TotalSATScore,
    CASE
      WHEN satscores.NumTstTakr IS NULL OR satscores.NumTstTakr = 0 THEN NULL
      ELSE ROUND(satscores.NumGE1500 * 100.0 / satscores.NumTstTakr, 2)
    END AS PercentageStudentsOver1500
  FROM frpm
  JOIN schools ON frpm.CDSCode = schools.CDSCode
  LEFT JOIN satscores ON satscores.cds = schools.CDSCode AND satscores.rtype = 'S'
  WHERE frpm."Enrollment (K-12)" > 0
    AND (COALESCE(frpm."Enrollment (K-12)",0) + COALESCE(frpm."Enrollment (Ages 5-17)",0)) > 500
    AND (
      frpm."Percent (%) Eligible FRPM (K-12)" > 0.60
      OR (satscores.NumTstTakr > 0 AND satscores.NumGE1500 * 1.0 / satscores.NumTstTakr > 0.30)
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
  RANK() OVER (PARTITION BY FRPMCategory ORDER BY TotalSATScore DESC) AS CategorySATRank
FROM base
ORDER BY "County Name", CountyEnrollmentRank, CategorySATRank;
```

### bird_0018

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：join_semantics
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'outer:ss."County Name"'], ['predicted_group_by', 'outer:frpm."County Name"'], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:aggregation_grain:sha256:808a6d0b60f32c4cd2de662be256a381e9fa94a7d857fc5a70d91afc631123eb;2:no_progress:sha256:808a6d0b60f32c4cd2de662be256a381e9fa94a7d857fc5a70d91afc631123eb;3:kept_candidate:no_progress']]
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
- 分组：['frpm."County Name"']
- 电商规则：[]
- 串库表：[]

```sql
SELECT COUNT(DISTINCT frpm.CDSCode) AS TotalSchools, frpm."County Name" AS "County Name", ROUND(AVG(satscores.NumTstTakr), 2) AS AvgTestTakers, ROUND(AVG(satscores.AvgScrRead + satscores.AvgScrMath + satscores.AvgScrWrite), 2) AS AvgTotalScore, ROUND(AVG(CAST(satscores.NumGE1500 AS REAL) * 100 / satscores.NumTstTakr), 2) AS AvgPercentScoring1500Plus, ROUND(AVG(frpm."Percent (%) Eligible FRPM (K-12)") * 100, 2) AS AvgFRPMPercentage, ROUND(AVG((CAST(STRFTIME('%Y', '2026-10-01') AS INTEGER) - CAST(STRFTIME('%Y', schools.OpenDate) AS INTEGER))), 2) AS AvgSchoolAgeInYears, SUM(CASE WHEN satscores.NumTstTakr <= 50 THEN 1 ELSE 0 END) AS SchoolsWithUnder50Testers, SUM(CASE WHEN satscores.NumTstTakr > 50 AND satscores.NumTstTakr <= 100 THEN 1 ELSE 0 END) AS SchoolsWith50To100Testers, SUM(CASE WHEN satscores.NumTstTakr > 100 AND satscores.NumTstTakr <= 250 THEN 1 ELSE 0 END) AS SchoolsWith100To250Testers FROM frpm JOIN schools ON frpm.CDSCode = schools.CDSCode JOIN satscores ON satscores.cds = schools.CDSCode WHERE frpm."Charter Funding Type" = 'Directly funded' AND frpm."County Name" = 'Fresno' AND satscores.rtype = 'S' AND satscores.NumTstTakr <= 250 GROUP BY frpm."County Name"
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
ORDER BY r."Math Score" DESC
LIMIT 1
```

### bird_0020

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:51b815f898f8951e69c142f1e3b7f4de8426852e90e66873c6f7049ae9e36359;2:projection_mismatch:sha256:03ee002b014b5c67e0b02fb326030ecdf1bbde960c2414991771b9109f0d4807;3:projection_mismatch:sha256:51b815f898f8951e69c142f1e3b7f4de8426852e90e66873c6f7049ae9e36359;4:accepted:']]
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
- 聚合：['count', 'avg', 'max']
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH SchoolInfo AS (SELECT s.CDSCode, s.School, s.District, s.Charter, f."Enrollment (K-12)" AS Enrollment, f."Free Meal Count (K-12)" * 1.0 / f."Enrollment (K-12)" AS FreeMealRate FROM schools AS s JOIN frpm AS f ON f.CDSCode = s.CDSCode WHERE s.County = 'Amador' AND s.StatusType = 'Active' AND f."Low Grade" = '9' AND f."High Grade" = '12' AND f."Enrollment (K-12)" > 0), SATData AS (SELECT si.CDSCode, sa.NumTstTakr, sa.NumGE1500, (sa.AvgScrRead + sa.AvgScrMath + sa.AvgScrWrite) AS TotalScore, CASE WHEN sa.NumTstTakr IS NULL THEN 'No SAT Data' WHEN (sa.AvgScrRead + sa.AvgScrMath + sa.AvgScrWrite) < 1200 THEN 'Below Average' WHEN (sa.AvgScrRead + sa.AvgScrMath + sa.AvgScrWrite) <= 1500 THEN 'Average' ELSE 'Above Average' END AS SATPerformanceLevel FROM SchoolInfo AS si LEFT JOIN satscores AS sa ON sa.cds = si.CDSCode AND sa.rtype = 'S'), EnrollmentRanked AS (SELECT si.School, si.Enrollment, ROW_NUMBER() OVER (ORDER BY si.Enrollment DESC) AS EnrollmentRank FROM SchoolInfo AS si) SELECT (SELECT COUNT(*) FROM SchoolInfo) AS TotalSchools, (SELECT ROUND(AVG(Enrollment), 2) FROM SchoolInfo) AS AvgEnrollment, (SELECT COUNT(*) FROM SchoolInfo WHERE Charter = 1) AS CharterSchools, (SELECT COUNT(*) FROM SchoolInfo WHERE Charter = 0) AS NonCharterSchools, (SELECT ROUND(AVG(FreeMealRate) * 100, 2) FROM SchoolInfo) AS AvgFRPMPercentage, (SELECT COUNT(DISTINCT District) FROM SchoolInfo) AS DistrictCount, (SELECT ROUND(AVG(TotalScore), 2) FROM SATData WHERE NOT TotalScore IS NULL) AS AvgSATScore, (SELECT ROUND(MAX(NumGE1500 * 100.0 / NumTstTakr), 2) FROM SATData WHERE NumTstTakr > 0) AS MaxPercentAbove1500, (SELECT School FROM EnrollmentRanked WHERE EnrollmentRank = 1) AS LargestSchool, (SELECT COUNT(*) FROM SchoolInfo WHERE FreeMealRate > 0.75) AS HighPovertySchools
```

### bird_0021

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'CategoryBreakdown:FreeMealCategory'], ['predicted_group_by', 'CategoryBreakdown:FreeMealCategory'], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=3;predicted=3'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:9f5e1b106c8c85335bb216e8cf0b68b1d24a84f2a86a902661355f0638cf02d4;2:missing_entity:sha256:34894324a40724990b26bdcd5b463b499f8d3fa19db4b39edb6c7bb0afd834a9;3:projection_mismatch:sha256:3e820826c67db8f8e44ae1f47ba0a46f692139f6034741e513da01819098654d;4:accepted:']]
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
- 聚合：['count', 'avg', 'group_concat']
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH SchoolMealStats AS (SELECT f.CDSCode, f."Free Meal Count (K-12)" AS FreeMealCount, f."FRPM Count (K-12)" AS FRPMCount, f."Enrollment (K-12)" AS Enrollment, f."Free Meal Count (K-12)" * 100.0 / f."Enrollment (K-12)" AS FreePercentage, f."FRPM Count (K-12)" * 100.0 / f."Enrollment (K-12)" AS FRPMPercentage, sc.Charter AS CharterFlag, CASE WHEN f."Free Meal Count (K-12)" > 600 THEN 'Very High' WHEN f."Free Meal Count (K-12)" > 500 THEN 'High' ELSE 'Moderate' END AS FreeMealCategory FROM frpm AS f JOIN schools AS sc ON sc.CDSCode = f.CDSCode WHERE f."County Name" = 'Los Angeles' AND f."Enrollment (K-12)" > 0 AND f."Free Meal Count (K-12)" > 500 AND f."FRPM Count (K-12)" < 700), SATData AS (SELECT s.cds, s.AvgScrRead + s.AvgScrMath + s.AvgScrWrite AS TotalSATScore FROM satscores AS s WHERE s.rtype = 'S' AND s.cname = 'Los Angeles'), CategoryBreakdown AS (SELECT FreeMealCategory, COUNT(*) AS CategoryCount FROM SchoolMealStats GROUP BY FreeMealCategory) SELECT (SELECT COUNT(*) FROM SchoolMealStats) AS TotalSchools, (SELECT ROUND(AVG(FreeMealCount), 2) FROM SchoolMealStats) AS AvgFreeMeals, (SELECT ROUND(AVG(FRPMCount), 2) FROM SchoolMealStats) AS AvgTotalFRPM, (SELECT ROUND(AVG(FreePercentage), 2) FROM SchoolMealStats) AS AvgFreePercentage, (SELECT ROUND(AVG(FRPMPercentage), 2) FROM SchoolMealStats) AS AvgFRPMPercentage, (SELECT COUNT(*) FROM SchoolMealStats WHERE CharterFlag = 1) AS CharterSchoolCount, (SELECT COUNT(*) FROM SchoolMealStats WHERE CharterFlag = 0) AS NonCharterSchoolCount, (SELECT ROUND(AVG(sd.TotalSATScore), 2) FROM SchoolMealStats AS sms JOIN SATData AS sd ON sd.cds = sms.CDSCode) AS AvgSATScore, (SELECT COUNT(*) FROM SchoolMealStats AS sms LEFT JOIN SATData AS sd ON sd.cds = sms.CDSCode WHERE sd.TotalSATScore IS NULL) AS SchoolsWithoutSATData, (SELECT GROUP_CONCAT(FreeMealCategory || ': ' || CategoryCount, '; ') FROM CategoryBreakdown) AS FreeMealCategoryBreakdown
```

### bird_0045

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'DistrictAverages:s.District'], ['predicted_group_by', 'DistrictAverages:s.District'], ['aggregation_only_in_cte', 'SchoolStats,DistrictAverages'], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=4;predicted=3'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:96a951821fa9ee660c9b4af505bbfb2c4faaf4330211dcef832b525a1b8dc3ef;2:accepted:']]
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
- 聚合：[]
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH SchoolStats AS (SELECT s.School AS School, ss.AvgScrWrite AS AvgScrWrite, ss.AvgScrRead AS AvgScrRead, ss.AvgScrMath AS AvgScrMath, (ss.AvgScrRead + ss.AvgScrMath + ss.AvgScrWrite) AS TotalSATScore, ss.NumTstTakr AS NumTstTakr, f."Enrollment (K-12)" AS "Enrollment (K-12)", ROUND(f."Percent (%) Eligible FRPM (K-12)" * 100, 2) AS FRPMPercentage, s.District AS District, RANK() OVER (ORDER BY ss.AvgScrWrite DESC) AS WriteScoreRank, RANK() OVER (ORDER BY (ss.AvgScrRead + ss.AvgScrMath + ss.AvgScrWrite) DESC) AS TotalScoreRank FROM schools AS s JOIN satscores AS ss ON ss.cds = s.CDSCode LEFT JOIN frpm AS f ON f.CDSCode = s.CDSCode WHERE s.AdmFName1 = 'Ricci' AND s.AdmLName1 = 'Ulrich'), DistrictAverages AS (SELECT s.District AS District, AVG(ss.AvgScrWrite) AS DistrictAvgWriteScore FROM schools AS s JOIN satscores AS ss ON ss.cds = s.CDSCode GROUP BY s.District) SELECT st.School AS School, st.AvgScrWrite AS AvgScrWrite, st.AvgScrRead AS AvgScrRead, st.AvgScrMath AS AvgScrMath, st.TotalSATScore AS TotalSATScore, st.NumTstTakr AS NumTstTakr, st."Enrollment (K-12)" AS "Enrollment (K-12)", st.FRPMPercentage AS FRPMPercentage, st.WriteScoreRank AS WriteScoreRank, st.TotalScoreRank AS TotalScoreRank, ROUND(da.DistrictAvgWriteScore, 2) AS DistrictAvgWriteScore, CASE WHEN st.AvgScrWrite > da.DistrictAvgWriteScore THEN 'Above District Average' WHEN st.AvgScrWrite = da.DistrictAvgWriteScore THEN 'Equal to District Average' ELSE 'Below District Average' END AS ComparisonToDistrictAvg, ROUND(st.AvgScrWrite - da.DistrictAvgWriteScore, 2) AS DifferenceFromDistrictAvg, ROUND(st.NumTstTakr * 100.0 / st."Enrollment (K-12)", 2) AS PercentageTakingSAT FROM SchoolStats AS st JOIN DistrictAverages AS da ON da.District = st.District ORDER BY st.WriteScoreRank
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
- 分类：sql_error
- 细分类：circuit_breaker
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:dbafdc8b48f79cadce2be6f2ba41393ef971394879c223a2e317d0a5d3f7ac39;2:no_progress:sha256:dbafdc8b48f79cadce2be6f2ba41393ef971394879c223a2e317d0a5d3f7ac39']]
- 错误类别：no_progress
- 脱敏错误：修复没有改变症状，已标记 no_progress 并熔断
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
SELECT
  schools.School AS SchoolName,
  schools.Website AS Website,
  schools.CharterNum AS CharterNumber,
  schools.FundingType AS FundingType,
  frpm."Enrollment (K-12)" AS TotalEnrollment,
  frpm."FRPM Count (K-12)" AS FRPMCount,
  ROUND(frpm."Percent (%) Eligible FRPM (K-12)" * 100, 2) AS FRPMPercentage,
  CASE
    WHEN frpm."Percent (%) Eligible FRPM (K-12)" > 0.75 THEN 'Very High Poverty'
    WHEN frpm."Percent (%) Eligible FRPM (K-12)" > 0.50 THEN 'High Poverty'
    WHEN frpm."Percent (%) Eligible FRPM (K-12)" > 0.25 THEN 'Moderate Poverty'
    ELSE 'Low Poverty'
  END AS PovertyLevel,
  RANK() OVER (ORDER BY frpm."Enrollment (K-12)" DESC) AS EnrollmentRank,
  satscores.NumTstTakr AS SATTestTakers,
  satscores.AvgScrRead AS AvgReadingScore,
  satscores.AvgScrMath AS AvgMathScore,
  satscores.AvgScrWrite AS AvgWritingScore,
  satscores.NumGE1500 AS StudentsOver1500,
  CASE
    WHEN satscores.NumTstTakr IS NULL OR satscores.NumTstTakr = 0 THEN 'No SAT Data'
    ELSE ROUND(CAST(satscores.NumGE1500 AS REAL) * 100 / satscores.NumTstTakr, 2) || '%'
  END AS PercentOver1500
FROM schools
JOIN frpm ON frpm.CDSCode = schools.CDSCode
LEFT JOIN satscores ON satscores.cds = schools.CDSCode AND satscores.rtype = 'S'
WHERE schools.Virtual = 'P'
  AND schools.Charter = 1
  AND schools.County = 'San Joaquin'
ORDER BY EnrollmentRank;
```

### bird_0062

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：missing_required_table
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'CountyStats:County'], ['predicted_group_by', ''], ['aggregation_only_in_cte', 'county_stats'], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=3;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:75bfe6f3bc2069b607e1a6d384525290465516088a90bb55bb4f62f1f1e3d7f8;2:cartesian_product:sha256:c3cb72c5eea9656c0dfa63c53fdc535864b0e60176825c159a5ef707ad8ff94c;3:projection_mismatch:sha256:75bfe6f3bc2069b607e1a6d384525290465516088a90bb55bb4f62f1f1e3d7f8;4:kept_candidate:projection_mismatch']]
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
WITH base AS (SELECT frpm.CDSCode AS CDSCode, frpm."School Name" AS School, frpm."District Name" AS District, frpm."County Name" AS County, frpm."Enrollment (K-12)" AS Enrollment, frpm."Free Meal Count (K-12)" AS FreeMealCount, (frpm."Free Meal Count (K-12)" * 1.0 / frpm."Enrollment (K-12)") * 100 AS FreePercentage FROM frpm JOIN schools ON frpm.CDSCode = schools.CDSCode WHERE schools.Charter = 0 AND frpm."County Name" = 'Los Angeles' AND frpm."Enrollment (K-12)" > 0), filtered AS (SELECT * FROM base WHERE FreePercentage < 18), county_stats AS (SELECT COUNT(*) AS TotalSchools, COUNT(*) AS LowFreeSchools, AVG(FreePercentage) AS CountyAvgFreePercent FROM filtered) SELECT f.CDSCode AS CDSCode, f.School AS School, f.District AS District, f.County AS County, f.Enrollment AS Enrollment, f.FreeMealCount AS FreeMealCount, ROUND(f.FreePercentage, 4) AS FreePercentage, CASE WHEN f.FreePercentage < 6 THEN 'Very Low' WHEN f.FreePercentage < 12 THEN 'Low' WHEN f.FreePercentage < 18 THEN 'Medium' ELSE 'High' END AS FreeCategory, ROW_NUMBER() OVER (ORDER BY f.FreePercentage ASC, f.CDSCode ASC) AS CountyRank, cs.TotalSchools AS TotalSchools, cs.LowFreeSchools AS LowFreeSchools, ROUND(cs.CountyAvgFreePercent, 4) AS CountyAvgFreePercent, ROUND(cs.LowFreeSchools * 100.0 / cs.TotalSchools, 2) || '%' AS PctLowFreeInCounty, cs.LowFreeSchools AS LATotalLowFree FROM filtered AS f CROSS JOIN county_stats AS cs ORDER BY f.FreePercentage ASC, f.CDSCode ASC
```

### bird_0066

- 数据库：california_schools
- 分类：sql_error
- 细分类：circuit_breaker
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'CountyStats:County'], ['predicted_group_by', 'CountyStats:County'], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=3;predicted=3'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:undefined_column:sha256:4add9b85dbbf256f0cb1eef511c0117dfa5e3550c55a5ffea06af06c443213c1;2:projection_mismatch:sha256:333670dac2764195a7790aeb9ee25bc5dbadf978b871db696af7de91e882a03e;3:projection_mismatch:sha256:4907fd701882615fa12770dca521a50d2b4a6a45a95e0240aa2636b4248a5629;4:no_progress:sha256:4907fd701882615fa12770dca521a50d2b4a6a45a95e0240aa2636b4248a5629']]
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
WITH DirectlyFundedSchools AS (
  SELECT
    s.School AS School,
    s.OpenDate AS OpenDate,
    STRFTIME('%Y', s.OpenDate) AS OpenYear,
    f."Enrollment (K-12)" AS Enrollment,
    f."FRPM Count (K-12)" AS FRPMCount,
    f."Percent (%) Eligible FRPM (K-12)" * 100 AS FRPMPercent,
    CASE
      WHEN f."Educational Option Type" = 'Traditional' THEN 'Traditional'
      ELSE 'Non-Traditional'
    END AS SchoolType,
    ss.AvgScrRead AS AvgScrRead,
    ss.AvgScrMath AS AvgScrMath,
    ss.AvgScrWrite AS AvgScrWrite,
    CASE
      WHEN ss.AvgScrRead IS NULL OR ss.AvgScrMath IS NULL OR ss.AvgScrWrite IS NULL THEN NULL
      ELSE ss.AvgScrRead + ss.AvgScrMath + ss.AvgScrWrite
    END AS TotalSATScore,
    s.County AS County
  FROM schools s
  JOIN frpm f ON f.CDSCode = s.CDSCode
  LEFT JOIN satscores ss ON ss.cds = s.CDSCode AND ss.rtype = 'S'
  WHERE s.FundingType = 'Directly funded'
    AND s.County = 'Stanislaus'
    AND STRFTIME('%Y', s.OpenDate) BETWEEN '2000' AND '2005'
    AND f."Enrollment (K-12)" > 0
),
CountyStats AS (
  SELECT
    County,
    COUNT(*) AS CountyTotalSchools,
    AVG(Enrollment) AS CountyAvgEnrollment,
    AVG(FRPMPercent) AS CountyAvgFRPMPercent
  FROM DirectlyFundedSchools
  GROUP BY County
)
SELECT
  d.School AS School,
  d.OpenDate AS OpenDate,
  d.OpenYear AS OpenYear,
  d.Enrollment AS Enrollment,
  d.FRPMCount AS FRPMCount,
  d.FRPMPercent AS FRPMPercent,
  d.SchoolType AS SchoolType,
  d.AvgScrRead AS AvgScrRead,
  d.AvgScrMath AS AvgScrMath,
  d.AvgScrWrite AS AvgScrWrite,
  d.TotalSATScore AS TotalSATScore,
  c.CountyTotalSchools AS CountyTotalSchools,
  c.CountyAvgEnrollment AS CountyAvgEnrollment,
  c.CountyAvgFRPMPercent AS CountyAvgFRPMPercent,
  CASE
    WHEN d.FRPMPercent > c.CountyAvgFRPMPercent THEN 'Above County Average'
    WHEN d.FRPMPercent < c.CountyAvgFRPMPercent THEN 'Below County Average'
    ELSE 'At County Average'
  END AS FRPMStatus,
  RANK() OVER (ORDER BY d.FRPMPercent DESC) AS FRPMRank,
  RANK() OVER (ORDER BY d.To
-- truncated
```

### bird_0069

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=3;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:c677bb6a35b15689671d950a0309e088b0f99e4d48abe34b4c28415ba85ca1f1;2:projection_mismatch:sha256:bbc8626d588f46358128f0e0cb511d2f8bc14eeff732c27d6bc1557d802ef2d9;3:projection_mismatch:sha256:de0d72713ed9be460b0082290189348765926b46cf08568ea89b21bd4e9669de;4:projection_mismatch:sha256:bbc8626d588f46358128f0e0cb511d2f8bc14eeff732c27d6bc1557d802ef2d9;5:projection_mismatch:sha256:de0d72713ed9be460b0082290189348765926b46cf08568ea89b21bd4e9669de']]
- 错误类别：projection_mismatch
- 脱敏错误：projection_mismatch: SOC 过滤放在 StateSpecialSchools CTE 外层：WHERE ss.SOC=<literal> OR ss.SOC LIKE <literal>；projection_mismatch: 问句点名的列 School Name 没有出现在投影或过滤中；projection_mismatch: 问句点名的列 District 没有出现在投影或过滤中
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
WITH StateSpecialSchools AS (
  SELECT
    s.CDSCode,
    s.NCESDist,
    s.School,
    s.Charter,
    s.ClosedDate,
    s.OpenDate,
    s.SOC
  FROM schools s
  WHERE s.DOCType = 'State Special Schools'
    AND s.SOC LIKE '3%'
)
SELECT
  ss.NCESDist AS "NCESDist",
  ss.School AS "School",
  CASE WHEN ss.Charter = 1 THEN 'Charter' ELSE 'Non-Charter' END AS "SchoolType",
  CASE WHEN ss.ClosedDate IS NULL THEN 'Active' ELSE 'Closed' END AS "CurrentStatus",
  date(ss.OpenDate) AS "OpeningDate",
  f."Enrollment (K-12)" AS "Enrollment",
  CASE
    WHEN f."Percent (%) Eligible FRPM (K-12)" > 0.75 THEN 'High'
    WHEN f."Percent (%) Eligible FRPM (K-12)" > 0.50 THEN 'Medium'
    WHEN f."Percent (%) Eligible FRPM (K-12)" > 0.25 THEN 'Low'
    ELSE 'Very Low'
  END AS "PovertyLevel",
  sa.AvgScrRead AS "AvgReadingScore",
  sa.AvgScrMath AS "AvgMathScore",
  sa.AvgScrWrite AS "AvgWritingScore",
  ROUND((COALESCE(sa.AvgScrRead,0) + COALESCE(sa.AvgScrMath,0) + COALESCE(sa.AvgScrWrite,0)) / 3.0, 2) AS "AvgTotalScore",
  RANK() OVER (ORDER BY f."Enrollment (K-12)" DESC) AS "EnrollmentRank"
FROM StateSpecialSchools ss
JOIN frpm f ON f.CDSCode = ss.CDSCode
LEFT JOIN satscores sa ON sa.cds = ss.CDSCode AND sa.rtype = 'S'
ORDER BY "EnrollmentRank" ASC;
```

### bird_0077

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=2'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:ed68cc7861af7a4254ad6c673415d84f3f350433b7d0e0e2e2833fcfa2013bdb;2:projection_mismatch:sha256:b6bac20361ad371766567d13e735895a1c02a26ed3c354da5fc0007098a4367b;3:projection_mismatch:sha256:87747a7ff493b4eb19ed2072bfffdf471909ebd2573220dcb4cd0639ef82d64a;4:projection_mismatch:sha256:41407be8daa3accacb43e45adc805da0b1aaf0da7c693e95de19bdc27a381ec8;5:projection_mismatch:sha256:87747a7ff493b4eb19ed2072bfffdf471909ebd2573220dcb4cd0639ef82d64a']]
- 错误类别：projection_mismatch
- 脱敏错误：projection_mismatch: 口径：FRPM 比例用 frpm `Percent (%) Eligible FRPM (K-12)` * 100 AS FRPMPercentage，不要仅用 Free Meal Count/Enrollment 重算；projection_mismatch: 县级过滤优先用 frpm.`County Name`（或 schools.County 与问句县名一致），不要混用错误县列导致漏行。
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
  ROUND(frpm."Percent (%) Eligible FRPM (Ages 5-17)" * 100, 2) AS "Percent (%) Eligible FRPM (Ages 5-17)",
  CASE
    WHEN frpm."Percent (%) Eligible FRPM (Ages 5-17)" > 0.75 THEN 'High Poverty'
    WHEN frpm."Percent (%) Eligible FRPM (Ages 5-17)" > 0.50 THEN 'Medium Poverty'
    ELSE 'Low Poverty'
  END AS "Poverty_Level",
  CASE
    WHEN schools.Charter = 1 THEN 'Yes'
    WHEN schools.Charter = 0 THEN 'No'
    ELSE 'Unknown'
  END AS "Is_Charter",
  satscores.NumTstTakr AS "Number of SAT Test Takers",
  satscores.AvgScrRead AS "Avg Reading Score",
  satscores.AvgScrMath AS "Avg Math Score",
  satscores.AvgScrWrite AS "Avg Writing Score",
  (satscores.AvgScrRead + satscores.AvgScrMath + satscores.AvgScrWrite) AS "Total SAT Score",
  RANK() OVER (ORDER BY frpm."Percent (%) Eligible FRPM (Ages 5-17)" DESC) AS "SAT Ranking",
  frpm."FRPM Count (Ages 5-17)" AS "FRPM Count",
  frpm."Enrollment (Ages 5-17)" AS "Enrollment"
FROM schools
JOIN frpm
  ON frpm.CDSCode = schools.CDSCode
LEFT JOIN satscores
  ON satscores.cds = schools.CDSCode AND satscores.rtype = 'S'
WHERE schools.County = 'Los Angeles'
  AND schools.GSserved = 'K-9'
  AND frpm."Enrollment (Ages 5-17)" > 0
ORDER BY frpm."Percent (%) Eligible FRPM (Ages 5-17)" DESC;
```

### bird_0078

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：join_semantics
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'outer:sbs.GSserved、sbs.school_count | SchoolsByGradeSpan:s.GSserved'], ['predicted_group_by', 'GradeSpanRank:GSserved'], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=3;predicted=3'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:3c4533a9149e6cf3da4e19795755fa04b0a8492c28e97b8c97dc22b30c4b7ca5;2:accepted:']]
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
WITH AdelantoSchools AS (SELECT s.CDSCode, s.GSserved, s.StatusType, f."Enrollment (K-12)" AS enrollment, f."Percent (%) Eligible FRPM (K-12)" AS frpm_pct, ss.AvgScrRead, ss.AvgScrMath, ss.AvgScrWrite FROM schools AS s JOIN frpm AS f ON f.CDSCode = s.CDSCode LEFT JOIN satscores AS ss ON ss.cds = s.CDSCode AND ss.rtype = 'S' WHERE s.City = 'Adelanto' AND s.StatusType = 'Active'), SchoolStats AS (SELECT *, CASE WHEN frpm_pct > 0.75 THEN 'High Poverty' WHEN frpm_pct > 0.50 THEN 'Medium Poverty' ELSE 'Low Poverty' END AS poverty_level FROM AdelantoSchools), GradeSpanRank AS (SELECT GSserved, COUNT(*) AS cnt, RANK() OVER (ORDER BY COUNT(*) DESC) AS grade_span_rank FROM SchoolStats GROUP BY GSserved), MostCommon AS (SELECT GSserved AS most_common_grade_span FROM GradeSpanRank WHERE grade_span_rank = 1) SELECT mc.most_common_grade_span AS most_common_grade_span, COUNT(*) AS school_count, SUM(CASE WHEN a.StatusType = 'Active' THEN 1 ELSE 0 END) AS active_schools, ROUND(AVG(a.enrollment), 2) AS avg_enrollment, SUM(a.enrollment) AS total_enrollment, ROUND(AVG(a.frpm_pct), 2) AS avg_frpm_percentage, COUNT(CASE WHEN a.poverty_level = 'High Poverty' THEN 1 END) AS high_poverty_schools, COUNT(CASE WHEN a.poverty_level = 'Medium Poverty' THEN 1 END) AS medium_poverty_schools, COUNT(CASE WHEN a.poverty_level = 'Low Poverty' THEN 1 END) AS low_poverty_schools, ROUND(AVG(a.AvgScrRead), 2) AS avg_reading_score, ROUND(AVG(a.AvgScrMath), 2) AS avg_math_score, ROUND(AVG(a.AvgScrWrite), 2) AS avg_writing_score FROM SchoolStats AS a JOIN MostCommon AS mc ON a.GSserved = mc.most_common_grade_span
```

### bird_0079

- 数据库：california_schools
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'CountyStats:County'], ['predicted_group_by', 'agg:County'], ['aggregation_only_in_cte', 'agg,ranked'], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=2;predicted=3'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:c163fd8782d2d79bc8a76e4c6044dbb35fc735881770d2fb8e94aceac5438416;2:projection_mismatch:sha256:3e820826c67db8f8e44ae1f47ba0a46f692139f6034741e513da01819098654d;3:projection_mismatch:sha256:c077cb907705b616d0ac06f3ee16e1e2ab067ee4ffa5991728558cbc4aa9ba49;4:projection_mismatch:sha256:3e820826c67db8f8e44ae1f47ba0a46f692139f6034741e513da01819098654d;5:accepted:']]
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
WITH base AS (SELECT s.County AS County, s.CDSCode AS CDSCode, s.School AS School, s.Charter AS CharterFlag, COALESCE(f."Enrollment (K-12)", 0) AS Enrollment, CASE WHEN COALESCE(f."Enrollment (K-12)", 0) > 0 THEN f."Free Meal Count (K-12)" * 1.0 / f."Enrollment (K-12)" ELSE NULL END AS FreeMealRate, (sa.AvgScrRead + sa.AvgScrMath + sa.AvgScrWrite) AS TotalSAT FROM schools AS s LEFT JOIN frpm AS f ON f.CDSCode = s.CDSCode LEFT JOIN satscores AS sa ON sa.cds = s.CDSCode AND sa.rtype = 'S' WHERE s.Virtual = 'F' AND s.County IN ('San Diego', 'Santa Barbara')), agg AS (SELECT County, COUNT(*) AS amount, SUM(CASE WHEN CharterFlag = 1 THEN 1 ELSE 0 END) AS CharterSchools, SUM(CASE WHEN CharterFlag = 0 THEN 1 ELSE 0 END) AS RegularSchools, AVG(Enrollment) AS AverageEnrollment, MAX(Enrollment) AS HighestEnrollment, MIN(Enrollment) AS LowestEnrollment, ROUND(AVG(FreeMealRate) * 100, 2) || '%' AS AvgFreeReducedMealPercentage, AVG(TotalSAT) AS AverageSATScore FROM base GROUP BY County), largest AS (SELECT County, School AS LargestVirtualSchool FROM (SELECT County, School, ROW_NUMBER() OVER (PARTITION BY County ORDER BY Enrollment DESC) AS rn FROM base) WHERE rn = 1), ranked AS (SELECT a.County AS County, a.amount AS amount, a.CharterSchools AS CharterSchools, a.RegularSchools AS RegularSchools, a.AverageEnrollment AS AverageEnrollment, a.HighestEnrollment AS HighestEnrollment, a.LowestEnrollment AS LowestEnrollment, a.AvgFreeReducedMealPercentage AS AvgFreeReducedMealPercentage, a.AverageSATScore AS AverageSATScore, l.LargestVirtualSchool AS LargestVirtualSchool, RANK() OVER (ORDER BY a.amount DESC) AS CountyRank FROM agg AS a JOIN largest AS l ON l.County = a.County) SELECT County, amount, CharterSchools, RegularSchools, AverageEnrollment, HighestEnrollment, LowestEnrollment, AvgFreeReducedMealPercentage, AverageSATScore, LargestVirtualSchool FROM ranked WHERE CountyRank = 1
```

### bird_0092

- 数据库：financial
- 分类：sql_error
- 细分类：circuit_breaker
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'DistrictStats:d.district_id、d.A2、d.A3、d.A11 | AccountActivity:a.district_id'], ['predicted_group_by', 'district_stats:a.district_id | account_activity:a.district_id'], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=5;predicted=9'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:2c718315931358661242ed038cebc3da61d92348ed7078da50fe3ee4604c0bf9;2:no_progress:sha256:2c718315931358661242ed038cebc3da61d92348ed7078da50fe3ee4604c0bf9']]
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
- 聚合：['count', 'sum', 'avg', 'group_concat']
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH female_owner_accounts AS (
  SELECT
    c.client_id,
    c.birth_date,
    a.account_id,
    a.district_id
  FROM client c
  JOIN disp d ON d.client_id = c.client_id AND d.type = 'OWNER'
  JOIN account a ON a.account_id = d.account_id
  WHERE c.gender = 'F'
),
district_stats AS (
  SELECT
    a.district_id,
    COUNT(DISTINCT c.client_id) AS female_clients,
    AVG(dt.A11) AS avg_salary,
    AVG(2026 - CAST(STRFTIME('%Y', c.birth_date) AS INTEGER)) AS avg_age
  FROM female_owner_accounts c
  JOIN account a ON a.account_id = c.account_id
  JOIN district dt ON dt.district_id = a.district_id
  GROUP BY a.district_id
),
account_activity AS (
  SELECT
    a.district_id,
    COUNT(DISTINCT a.account_id) AS total_accounts,
    COUNT(l.loan_id) AS total_loans,
    AVG(l.amount) AS avg_loan_amount,
    SUM(CASE WHEN l.status = 'A' THEN 1 ELSE 0 END) AS active_loans,
    SUM(CASE WHEN l.status = 'B' THEN 1 ELSE 0 END) AS completed_loans,
    SUM(CASE WHEN l.status = 'C' THEN 1 ELSE 0 END) AS defaulted_loans
  FROM account a
  JOIN disp d ON d.account_id = a.account_id AND d.type = 'OWNER'
  JOIN client c ON c.client_id = d.client_id AND c.gender = 'F'
  LEFT JOIN loan l ON l.account_id = a.account_id
  GROUP BY a.district_id
),
qualified AS (
  SELECT
    ds.district_id,
    ds.female_clients,
    ds.avg_salary,
    ds.avg_age,
    aa.total_accounts,
    aa.total_loans,
    aa.avg_loan_amount,
    aa.active_loans,
    aa.completed_loans,
    aa.defaulted_loans,
    dt.A3 AS region,
    RANK() OVER (PARTITION BY dt.A3 ORDER BY ds.avg_salary DESC) AS salary_rank_in_region
  FROM district_stats ds
  JOIN account_activity aa ON aa.district_id = ds.district_id
  JOIN district dt ON dt.district_id = ds.district_id
  WHERE ds.avg_salary BETWEEN 6000 AND 10000
    AND ds.female_clients >= 5
    AND aa.total_loans > 0
)
SELECT
  COUNT(DISTINCT q.district_id) AS district_count,
  SUM(q.female_clients) AS total_female_clients,
  AVG(q.avg_salary) AS average_female_salary,
  ROUND(A
-- truncated
```

### bird_0097

- 数据库：financial
- 分类：other_result_mismatch
- 细分类：join_semantics
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'ClientLoanInfo:d.client_id、d.type、a.frequency | ClientTransactions:d.client_id | ClientCards:d.client_id'], ['predicted_group_by', 'ClientLoanInfo:da.client_id | Transactions:da.client_id | Cards:da.client_id'], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=8;predicted=10'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:cf9ed23a838405f2782334626c2c526add315f727864dce543091327fc8f8d85;2:accepted:']]
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
WITH DisponentAccounts AS (SELECT DISTINCT d.client_id, a.account_id FROM disp AS d JOIN account AS a ON d.account_id = a.account_id WHERE d.type = 'DISPONENT' AND a.frequency = 'POPLATEK PO OBRATU'), ClientLoanInfo AS (SELECT da.client_id, COUNT(l.loan_id) AS loan_count, AVG(l.amount) AS avg_loan_amount, SUM(CASE WHEN l.status = 'A' THEN 1 ELSE 0 END) AS active_loans, SUM(CASE WHEN l.status = 'B' THEN 1 ELSE 0 END) AS completed_loans FROM DisponentAccounts AS da LEFT JOIN loan AS l ON l.account_id = da.account_id GROUP BY da.client_id), Transactions AS (SELECT da.client_id, COUNT(t.trans_id) AS transaction_count, SUM(CASE WHEN t.type = 'PRIJEM' THEN t.amount ELSE 0 END) AS total_income, SUM(CASE WHEN t.type = 'VYDAJ' THEN t.amount ELSE 0 END) AS total_expense, MAX(t.date) AS last_transaction_date FROM DisponentAccounts AS da LEFT JOIN trans AS t ON t.account_id = da.account_id GROUP BY da.client_id), Cards AS (SELECT da.client_id, COUNT(c.card_id) AS card_count, GROUP_CONCAT(DISTINCT c.type) AS card_types FROM DisponentAccounts AS da LEFT JOIN disp AS d2 ON d2.account_id = da.account_id LEFT JOIN card AS c ON c.disp_id = d2.disp_id GROUP BY da.client_id) SELECT cl.client_id AS client_id, cl.gender AS gender, cl.birth_date AS birth_date, di.A2 AS district_name, di.A3 AS region, COALESCE(li.loan_count, 0) AS loan_count, COALESCE(li.avg_loan_amount, 0) AS avg_loan_amount, COALESCE(li.active_loans, 0) AS active_loans, COALESCE(li.completed_loans, 0) AS completed_loans, COALESCE(tx.transaction_count, 0) AS transaction_count, COALESCE(tx.total_income, 0) AS total_income, COALESCE(tx.total_expense, 0) AS total_expense, COALESCE(tx.total_income, 0) - COALESCE(tx.total_expense, 0) AS net_balance, tx.last_transaction_date AS last_transaction_date, COALESCE(cd.card_count, 0) AS card_count, cd.card_types AS card_types, CASE WHEN COALESCE(cd.card_count, 0) > 0 AND COALESCE(li.loan_count, 0) > 0 THEN 'Full Service Client' WHEN COALESCE(li.loan_count, 0) > 0 THEN 'Loan Only Clien
-- truncated
```

### bird_0100

- 数据库：financial
- 分类：sql_error
- 细分类：circuit_breaker
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', 'client_loan_status:s.client_id'], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=4;predicted=5'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:b7855885e11aa94a2c4b94ded0a09daac8c1f5b2873a3bf209ed9b5f1664698b;2:no_progress:sha256:b7855885e11aa94a2c4b94ded0a09daac8c1f5b2873a3bf209ed9b5f1664698b']]
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
- 聚合：['count', 'avg', 'sum', 'min', 'max']
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH sokolov_female_owners AS (
  SELECT DISTINCT
    c.client_id,
    CAST(strftime('%Y', c.birth_date) AS INTEGER) AS birth_year,
    a.account_id,
    CAST(strftime('%Y', a.date) AS INTEGER) AS account_year
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
    s.client_id,
    MAX(CASE WHEN l.loan_id IS NOT NULL THEN 1 ELSE 0 END) AS has_loan,
    MAX(CASE WHEN l.status = 'A' THEN 1 ELSE 0 END) AS has_good_loan,
    MAX(CASE WHEN l.status = 'D' THEN 1 ELSE 0 END) AS has_debt
  FROM sokolov_female_owners s
  LEFT JOIN loan l ON l.account_id = s.account_id
  GROUP BY s.client_id
)
SELECT
  COUNT(DISTINCT s.client_id) AS total_female_clients,
  ROUND(AVG(s.account_year - s.birth_year), 2) AS avg_age_at_account_opening,
  SUM(cls.has_loan) AS clients_with_loans,
  SUM(cls.has_good_loan) AS clients_with_good_loans,
  SUM(cls.has_debt) AS clients_with_debt,
  MIN(s.account_year) AS earliest_account_year,
  MAX(s.account_year) AS latest_account_year
FROM sokolov_female_owners s
JOIN client_loan_status cls ON cls.client_id = s.client_id;
```

### bird_0104

- 数据库：financial
- 分类：other_result_mismatch
- 细分类：other_result_mismatch
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', ''], ['predicted_group_by', ''], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=5;predicted=6'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '']]
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
WITH TransactionDetails AS (SELECT t.trans_id, t.account_id, t.date AS transaction_date, t.amount, t.balance, a.date AS account_opening_date, a.district_id, d.A2 AS district_name, d.A3 AS region FROM trans AS t JOIN account AS a ON t.account_id = a.account_id JOIN district AS d ON a.district_id = d.district_id WHERE t.amount = 840 AND t.date = '1998-10-14'), AccountOwners AS (SELECT td.trans_id, c.client_id, c.gender, c.birth_date FROM TransactionDetails AS td LEFT JOIN disp AS dp ON dp.account_id = td.account_id AND dp.type = 'OWNER' LEFT JOIN client AS c ON dp.client_id = c.client_id) SELECT td.account_id AS account_id, td.account_opening_date AS account_opening_date, td.transaction_date AS transaction_date, CAST((CAST(STRFTIME('%Y', td.transaction_date) AS INTEGER) - CAST(STRFTIME('%Y', td.account_opening_date) AS INTEGER)) * 365 + (CAST(STRFTIME('%m', td.transaction_date) AS INTEGER) - CAST(STRFTIME('%m', td.account_opening_date) AS INTEGER)) * 30 + (CAST(STRFTIME('%d', td.transaction_date) AS INTEGER) - CAST(STRFTIME('%d', td.account_opening_date) AS INTEGER)) AS INTEGER) AS days_account_open_before_transaction, td.amount AS amount, td.balance AS balance, td.district_name AS district_name, td.region AS region, ao.client_id AS client_id, CASE ao.gender WHEN 'M' THEN 'Male' WHEN 'F' THEN 'Female' ELSE 'Unknown' END AS gender_full, CAST(STRFTIME('%Y', td.transaction_date) AS INTEGER) - CAST(STRFTIME('%Y', ao.birth_date) AS INTEGER) - CASE WHEN (STRFTIME('%m-%d', td.transaction_date) < STRFTIME('%m-%d', ao.birth_date)) THEN 1 ELSE 0 END AS age_at_transaction, (SELECT COUNT(*) FROM trans AS t2 WHERE t2.account_id = td.account_id AND t2.date <= td.transaction_date) AS total_transactions_to_date, (SELECT COUNT(*) FROM card AS cd JOIN disp AS dp2 ON cd.disp_id = dp2.disp_id WHERE dp2.account_id = td.account_id) AS cards_issued, CASE WHEN EXISTS(SELECT 1 FROM loan AS l WHERE l.account_id = td.account_id AND l.date <= td.transaction_date) THEN 'Yes' ELSE 'No' END AS has_
-- truncated
```

### bird_0105

- 数据库：financial
- 分类：sql_error
- 细分类：circuit_breaker
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'ClientsInDistrict:d.district_id'], ['predicted_group_by', 'clients_in_district:c.district_id | trans_stats:t.account_id'], ['aggregation_only_in_cte', 'district_info,clients_in_district,trans_stats'], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=5;predicted=6'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:e051b53ad1011e5a4ad396b384f80bb79cf69d32aa40a2eeb6d33cbed7d6d9a1;2:projection_mismatch:sha256:7e5763de39082d84afd4eb8f045a16ba98e8f5d74cabb2f0f883d54bb2ca7b6c;3:no_progress:sha256:7e5763de39082d84afd4eb8f045a16ba98e8f5d74cabb2f0f883d54bb2ca7b6c']]
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
         AVG((CAST(STRFTIME('%Y', la.loan_date) AS INTEGER) - CAST(STRFTIME('%Y', c.birth_date) AS INTEGER))) AS avg_client_age
  FROM client c
  JOIN loan_account la ON la.district_id = c.district_id
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
      
-- truncated
```

### bird_0111

- 数据库：financial
- 分类：other_result_mismatch
- 细分类：join_semantics
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'ClientInfo:d.account_id | AccountActivity:account_id | LoanStatus:account_id'], ['predicted_group_by', 'AccountActivity:ai.account_id'], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=5;predicted=5'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:c9a2f314bb2342f210f9a699c45e6b266f217fda2129f5255ed017ddf2888f15;2:accepted:']]
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
- 聚合：['count', 'avg', 'sum']
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH AccountsInLitomerice1996 AS (SELECT a.account_id, a.date AS open_date FROM account AS a JOIN district AS d ON a.district_id = d.district_id WHERE d.A2 = 'Litomerice' AND STRFTIME('%Y', a.date) = '1996'), ClientInfo AS (SELECT ai.account_id, c.client_id, c.gender, c.birth_date FROM AccountsInLitomerice1996 AS ai JOIN disp AS dp ON ai.account_id = dp.account_id JOIN client AS c ON dp.client_id = c.client_id), AccountActivity AS (SELECT ai.account_id, COUNT(t.trans_id) AS txn_count, SUM(CASE WHEN t.type = 'PRIJEM' THEN t.amount ELSE 0 END) AS deposits FROM AccountsInLitomerice1996 AS ai LEFT JOIN trans AS t ON ai.account_id = t.account_id AND STRFTIME('%Y', t.date) = '1996' GROUP BY ai.account_id), LoanStatus AS (SELECT ai.account_id, l.loan_id, l.amount FROM AccountsInLitomerice1996 AS ai LEFT JOIN loan AS l ON ai.account_id = l.account_id) SELECT (SELECT COUNT(*) FROM AccountsInLitomerice1996) AS total_accounts, (SELECT COUNT(*) FROM (SELECT account_id FROM ClientInfo GROUP BY account_id HAVING COUNT(DISTINCT client_id) > 1)) AS accounts_with_multiple_clients, (SELECT AVG(1996 - CAST(STRFTIME('%Y', birth_date) AS INTEGER)) FROM ClientInfo) AS average_client_age, (SELECT COUNT(*) FROM ClientInfo WHERE gender = 'M') AS total_male_clients, (SELECT COUNT(*) FROM ClientInfo WHERE gender = 'F') AS total_female_clients, (SELECT SUM(txn_count) FROM AccountActivity) AS total_transactions_in_1996, (SELECT SUM(deposits) FROM AccountActivity) AS total_deposits_in_1996, (SELECT COUNT(loan_id) FROM LoanStatus) AS total_loans, (SELECT AVG(amount) FROM LoanStatus WHERE NOT loan_id IS NULL) AS avg_loan_amount, (SELECT COUNT(DISTINCT account_id) FROM LoanStatus WHERE NOT loan_id IS NULL) AS accounts_with_loans, (SELECT AVG(CASE WHEN CAST(STRFTIME('%m', open_date) AS INTEGER) BETWEEN 1 AND 3 THEN 100.0 ELSE 0 END) FROM AccountsInLitomerice1996) AS percent_opened_q1, (SELECT AVG(CASE WHEN CAST(STRFTIME('%m', open_date) AS INTEGER) BETWEEN 4 AND 6 THEN 100.0 ELSE 0 END) FROM Account
-- truncated
```

### bird_0113

- 数据库：financial
- 分类：sql_error
- 细分类：circuit_breaker
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'ClientTransactions:LC.client_id、LC.birth_date、LC.age_at_loan、d.A2、d.A3 | CardInfo:LC.client_id'], ['predicted_group_by', 'CardInfo:d.client_id'], ['aggregation_only_in_cte', ''], ['missing_output_labels', 'None'], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=11;predicted=9'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:408e406f46ad7e8d7d6d4e8abb21de781f4fd0f689d8a217ef8847606a79b24b;2:worker_failed:sha256:c348e066d84d6d01e83a44b1d5f913ed971cf69fbc8cea332d379ef4306d743d;3:no_progress:sha256:c348e066d84d6d01e83a44b1d5f913ed971cf69fbc8cea332d379ef4306d743d']]
- 错误类别：no_progress
- 脱敏错误：SQLite 子进程异常退出
- 上下文召回：1.0
- 引用表召回：1.0
- 维度覆盖：None
- 实体覆盖：None
- 度量覆盖：1.0
- 种子表：['card', 'client', 'loan', 'trans', 'disp', 'account', 'district', 'order']
- 引用表：['account', 'card', 'client', 'disp', 'district', 'loan', 'trans']
- 投影：['birth_date', 'age_at_loan', 'district_name', 'region', 'transaction_count', 'total_income', 'total_expense', 'expense_to_income_ratio', 'max_balance', 'min_balance', 'card_count', 'card_types', 'previous_loans']
- 聚合：['count', 'sum', 'max', 'min']
- 分组：[]
- 电商规则：[]
- 串库表：[]

```sql
WITH LoanClient AS (SELECT l.loan_id, l.account_id, l.date AS loan_date, l.amount AS loan_amount, c.client_id, c.birth_date, c.district_id FROM loan AS l JOIN account AS a ON l.account_id = a.account_id JOIN disp AS d ON d.account_id = a.account_id AND d.type = 'OWNER' JOIN client AS c ON d.client_id = c.client_id WHERE l.amount = 98832 AND l.date = '1996-01-03'), ClientTransactions AS (SELECT t.account_id, t.type, t.amount, t.balance FROM trans AS t JOIN LoanClient AS lc ON t.account_id = lc.account_id WHERE t.date < lc.loan_date AND t.type IN ('PRIJEM', 'VYDAJ')), CardInfo AS (SELECT d.client_id, COUNT(c.card_id) AS card_count, GROUP_CONCAT(c.type) AS card_types FROM card AS c JOIN disp AS d ON c.disp_id = d.disp_id GROUP BY d.client_id) SELECT lc.birth_date AS birth_date, CAST(STRFTIME('%Y', lc.loan_date) AS INTEGER) - CAST(STRFTIME('%Y', lc.birth_date) AS INTEGER) - CASE WHEN STRFTIME('%m-%d', lc.loan_date) < STRFTIME('%m-%d', lc.birth_date) THEN 1 ELSE 0 END AS age_at_loan, di.A2 AS district_name, di.A3 AS region, (SELECT COUNT(*) FROM ClientTransactions) AS transaction_count, (SELECT SUM(amount) FROM ClientTransactions WHERE type = 'PRIJEM') AS total_income, (SELECT SUM(amount) FROM ClientTransactions WHERE type = 'VYDAJ') AS total_expense, ROUND((SELECT SUM(amount) FROM ClientTransactions WHERE type = 'VYDAJ') * 100.0 / (SELECT SUM(amount) FROM ClientTransactions WHERE type = 'PRIJEM'), 2) AS expense_to_income_ratio, (SELECT MAX(balance) FROM ClientTransactions) AS max_balance, (SELECT MIN(balance) FROM ClientTransactions) AS min_balance, COALESCE(ci.card_count, 0) AS card_count, ci.card_types AS card_types, (SELECT COUNT(*) FROM loan AS l2 JOIN account AS a2 ON l2.account_id = a2.account_id JOIN disp AS d2 ON d2.account_id = a2.account_id AND d2.type = 'OWNER' WHERE d2.client_id = lc.client_id) AS previous_loans FROM LoanClient AS lc JOIN district AS di ON lc.district_id = di.district_id LEFT JOIN CardInfo AS ci ON ci.client_id = lc.client_id
```

### bird_0119

- 数据库：financial
- 分类：sql_error
- 细分类：circuit_breaker
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'AccountStats:a.account_id | ClientDetails:a.account_id | LoanInfo:a.account_id'], ['predicted_group_by', 'AccountStats:ai.account_id | ClientDetails:ai.account_id | LoanInfo:ai.account_id'], ['aggregation_only_in_cte', 'AccountStats,ClientDetails,LoanInfo'], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=8;predicted=8'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:b51b818be628af807785d397426595bb3ba3e019aeacf72e77f170dfad7e1c29;2:projection_mismatch:sha256:2013c7cd838e3f3a287fe3ca8b37670ebf77877d40939671de35ef755caa9a3f;3:no_progress:sha256:2013c7cd838e3f3a287fe3ca8b37670ebf77877d40939671de35ef755caa9a3f']]
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
  SELECT ai.account_id,
         COUNT(t.trans_id) AS transaction_count,
         SUM(CASE WHEN t.type = 'PRIJEM' THEN t.amount ELSE 0 END) AS total_income,
         SUM(CASE WHEN t.type = 'VYDAJ' THEN t.amount ELSE 0 END) AS total_expense,
         MAX(t.balance) - MIN(t.balance) AS balance_volatility
  FROM AccountsIn1993 ai
  LEFT JOIN trans t ON t.account_id = ai.account_id
  GROUP BY ai.account_id
),
ClientDetails AS (
  SELECT ai.account_id,
         COUNT(DISTINCT c.client_id) AS client_count,
         GROUP_CONCAT(DISTINCT c.gender) AS owner_gender,
         AVG((JULIANDAY(ai.account_open_date) - JULIANDAY(c.birth_date)) / 365.25) AS avg_client_age
  FROM AccountsIn1993 ai
  LEFT JOIN disp d ON d.account_id = ai.account_id
  LEFT JOIN client c ON c.client_id = d.client_id
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
SELECT ai.account_id AS account_id,
       ds.A2 AS district_name,
       ds.A3 AS district_region,
       CASE
         WHEN ds.A10 < 50000 THEN 'Rural'
         WHEN ds.A10 < 200000 THEN 'Semi-Urban'
         ELSE 'Urban'
       END AS urbanization_category,
       ast.transaction_count AS transaction_count,
       (COALESCE(ast.total_income, 0) - COALESCE(ast.total_expense, 0)) AS net_cash_flow,
       ast.balance_volatility AS balance_volatility,
      
-- truncated
```

### bird_0121

- 数据库：financial
- 分类：sql_error
- 细分类：circuit_breaker
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'TransactionStats:t.account_id | LoanInfo:l.account_id'], ['predicted_group_by', 'TransactionStats:t.account_id | LoanInfo:l.account_id'], ['aggregation_only_in_cte', 'TransactionStats,LoanInfo'], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=8;predicted=6'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:undefined_column:sha256:f96aca447d43a855657517f9ba210bf5a344fbb7d3409a00ed2fb291b7f6500c;2:no_progress:sha256:f96aca447d43a855657517f9ba210bf5a344fbb7d3409a00ed2fb291b7f6500c']]
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
  SELECT a.account_id, a.date AS opening_date, a.district_id
  FROM account a
  JOIN district d ON a.district_id = d.district_id
  WHERE d.A2 = 'Prachatice'
),
OwnerInfo AS (
  SELECT di.account_id, c.client_id, c.gender, c.birth_date
  FROM disp di
  JOIN client c ON di.client_id = c.client_id
  WHERE di.type = 'OWNER'
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
           WHEN SUM(CASE WHEN l.status = 'A' THEN 1 ELSE 0 END) > 0 THEN 'Has Active Loan'
           WHEN SUM(CASE WHEN l.status = 'B' THEN 1 ELSE 0 END) > 0 THEN 'Has Completed Loan'
           WHEN SUM(CASE WHEN l.status = 'C' THEN 1 ELSE 0 END) > 0 THEN 'Has Defaulted Loan'
           WHEN SUM(CASE WHEN l.status = 'D' THEN 1 ELSE 0 END) > 0 THEN 'Has Defaulted Loan'
           ELSE 'No Loans'
         END AS loan_status
  FROM loan l
  GROUP BY l.account_id
)
SELECT
  ap.account_id AS account_id,
  ap.opening_date AS opening_date,
  d.A2 AS district_name,
  d.A3 AS region,
  oi.gender AS gender,
  CAST(STRFTIME('%Y', '2026-10-01') AS INTEGER) - CAST(STRFTIME('%Y', oi.birth_date) AS INTEGER) AS client_age,
  COALESCE(ts.transaction_count, 0) AS transaction_count,
  COALESCE(ts.total_income, 0) AS total_income,
  COALESCE(ts.total_expense, 0) AS total_expense,
  COALESCE(ts.total_income, 0) - COALESCE(ts.total_expense, 0) AS net_balance,
  COALESCE(ts.max_balance, 0) AS max_balance,
  COALESCE(li.loan_count, 0) AS loan_count,
  COALESCE(li.total_loan_amount, 0) AS total_loan_amount,
  COALESCE(li.loan_status, 'No Loans') AS 
-- truncated
```

### bird_0123

- 数据库：financial
- 分类：sql_error
- 细分类：circuit_breaker
- 症状：[['missing_projections', ''], ['extra_projections', ''], ['projection_order', ''], ['gold_group_by', 'LoanStatistics:account_id | TransactionSummary:account_id'], ['predicted_group_by', 'loan_stats:l.account_id | trans_summary:t.account_id'], ['aggregation_only_in_cte', ''], ['missing_output_labels', ''], ['missing_filter_literals', ''], ['missing_dedup_key', ''], ['refanout_after_dedup', ''], ['aggregate_source_grain', ''], ['missing_group_identifier', ''], ['wrong_entity_literal', ''], ['category_scope', ''], ['join_shape_difference', 'gold=5;predicted=5'], ['runtime_clock', ''], ['recursive_cte', ''], ['repair_trace', '1:projection_mismatch:sha256:f54e8e0129131c8241e3c0e737e96fafbe9411a066307013fb2d4f08f1d46ef5;2:no_progress:sha256:f54e8e0129131c8241e3c0e737e96fafbe9411a066307013fb2d4f08f1d46ef5']]
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
  hs.district_name AS district_name,
  hs.region_name AS region_name,
  ls.max_loan_amount AS max_loan_amount,
  ROUND(ls.avg_loan_amount, 2) AS avg_loan_amount,
  ls.loan_count AS loan_count,
  oi.gender AS gender,
  oi.age AS age,
  CASE
    WHEN COALESCE(ts.total_income,0) >= 100000 THEN 'High Income'
    WHEN COALESCE(ts.total_income,0) >= 50000 THEN 'Medium Income'
    ELSE 'Low Income'
  END AS income_category,
  COALESCE(ts.transaction_count, 0) AS transaction_count,
  CASE
    WHEN ts.total_income IS NULL OR ts.total_income = 0 THEN NULL
    ELSE ROUND((ts.total_income - ts.total_expense) * 1.0 / ts.total_income, 4)
  END AS savings_ratio,
  RANK() OVER (PARTITION BY hs.region_name ORDER BY ls.max_loan_amount DESC) AS region_loan_rank
FROM account a
JOIN high_salary_districts hs ON a.district_id = hs.district_id
JOIN loan_stats ls ON a.account_id = ls.account_id
JOIN owner_info oi
-- truncated
```
