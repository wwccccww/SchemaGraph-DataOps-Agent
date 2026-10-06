"""构造问数 Prompt。Gold SQL 和评测标签不得进入这里。"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence

from app.agents.text_to_sql.contract import AnswerContract, format_answer_contract
from app.schemas.retrieval import ToolHit

PROMPT_VERSION = "text-to-sql-v3"
GENERIC_PROMPT_VERSION = "text-to-sql-generic-v49"
SYSTEM_PROMPT = (
    "你是 PostgreSQL 只读 SQL 生成器。只输出一条 SELECT 或 WITH ... SELECT，"
    "不要解释，不要写入数据，不要使用未给出的工具。"
)
_GENERIC_SHAPE_TAIL = (
    "若问句列举多项属性或 characteristics，最终 SELECT 应逐条回答，并为每列写清晰的 AS 别名。"
    "charter school、grades served、SAT performance level 等语义优先从 schools/satscores 等实体表取字段，"
    "SAT performance level 用 AvgScrRead+AvgScrMath+AvgScrWrite 总和（不要除以 3）做 CASE；"
    "标签用 No SAT Data、Below Average（<1200）、Average（1200–1500）、Above Average（>1500）；"
    "satscores 用 LEFT JOIN 保留无 SAT 学校。free meal rate 分母需 Enrollment (K-12) > 0。"
    "IsCharterSchool 用 schools.Charter：1→Yes、0→No、NULL→Unknown。"
    "Financial：region 用 district.A3；running OK / 正常贷款计数 status='C'；disp.type='OWNER' 取账户持有人；"
    "最年长女性→district_id 子查询再 JOIN account，ORDER BY district.A11 DESC LIMIT 1；"
    "薪资差第二列写 (SELECT MAX(A11)-MIN(A11) FROM district) 表达式（不要 AS 子查询文本别名，勿在 ORDER BY 里相关 AVG）。"
    "1993 POPLATEK PO OBRATU：account frequency='POPLATEK PO OBRATU' 且 STRFTIME('%Y',date)='1993'；"
    "trans PRIJEM/VYDAJ；loan status A=running、B=finished、C=defaulted（勿把 C 当 running）。"
    "State Special Schools：DOCType='State Special Schools'；SchoolType Charter/Non-Charter；AvgTotalScore 三科/3。"
    "loan→account→trans 链接；overall 对比按 loan_size_category 分组 JOIN，勿全局 CROSS JOIN。"
    "running OK 占比：CTE 内 CAST(SUM(CASE status='C' THEN 1 END) AS REAL)*100/COUNT(status) AS percentage_running_ok，"
    "最终 SELECT ROUND(percentage_running_ok,2) 与 ROUND(avg_loan_amount,2)，avg_duration 不 ROUND。"
    "COE charter：frpm.`District Name` 与 `Charter School (Y/N)`=1；CharterSchoolName=frpm.`School Name`；"
    "FRPM 分档严格 >0.75/>0.50；YearOpened 文本年；PercentageAbove1500=NumGE1500/NumTstTakr（rtype=S）。"
    "Magnet+SAT>500：SOCType/EdOpsName 来自 schools；FRPM  poverty 用小数列与 High/Moderate/Low/Very Low Poverty；"
    "SAT 分类 Excellent/Good/Average/Below Average；CountyRank 用 DENSE_RANK。"
    "最高 Reading：RANK+ReadingRank=1；frpm Ages 5-17；Percent1500+=NumGE1500/NumTstTakr；GSoffered。"
    "Top-5 FRPM SOC=66：RANK+FRPMRank<=5；rtype='S'；EligibilityRate 带 % 后缀；Very High FRPM 分档。"
    "CA 学校过滤：Unified DOC=54，Intermediate/Middle SOC=62；LA 县用 schools.County。"
    "Top-10 FRPM：RANK()+frpm_rank<=10；Enrollment>500 题 TotalEnrollment=K-12+Ages 5-17，"
    "FRPMCategory=High/Medium/Low FRPM（小数>=0.75/0.50），satscores rtype='S'；"
    "IsCharter 来自 frpm `Charter School (Y/N)`。"
    "LA 餐食聚合：Free Meal Count>500 且 FRPM Count<700（不是 Enrollment<700）；"
    "CategoryBreakdown+GROUP_CONCAT 子查询；Very High/High/Moderate 按 free meal count。"
    "Stanislaus Directly funded：FundingType='Directly funded'；FRPM 用小数列；"
    "CountyStats JOIN（勿 CROSS JOIN 单行 county）；FRPMStatus 与县均值 Above/Below/At County Average。"
    "Virtual 学校：schools.Virtual 为 F/P/N；fully virtual 过滤 Virtual='F'，partially Virtual='P'；"
    "VirtualStatus 用 CASE 输出 Fully Virtual 等标签。"
    "California schools：县名/学区/学校名与 free meal、NSLP、Enrollment 等优先用 frpm 带空格列名；"
    "Magnet、GSserved、Charter 等在 schools；问句同时涉及 magnet/grade span 与 NSLP/Provision 时必须 JOIN frpm 与 schools。"
    "SQLite 输出列别名若含空格或括号，必须与冻结契约一致并使用双引号。"
    "窗口函数（RANK/DENSE_RANK/ROW_NUMBER）写在最终 SELECT 中，不要在同一层再对窗口列做 GROUP BY；"
    "可先 CTE 算基础列，再在外层 SELECT 窗口函数并 ORDER BY。"
    "PerformanceCategory 为 SAT 分档；PerformanceClassification 为 FRPM 与 SAT 对比"
    "（Expected performance / despite high FRPM 等），勿把两列都写成 SAT Below/Average/Above 标签。"
    "问句含 unexpectedly well/poorly given FRPM：PerformanceCategory 用 High/Medium/Low（≥1500/≥1200）；"
    "PerformanceClassification 用 FRPM 小数阈值与 despite high/low FRPM 文案；"
    "UnabbreviatedMailingAddress 投影 schools.MailStreet；非 charter 用 frpm Charter School (Y/N)=0。"
    "两县指标比值：Metric 列文案以 Ratio 结尾（如 Total Schools Ratio）；High FRPM 校用 Percent FRPM>0.5；"
    "FRPM 学生总量用 SUM(FRPM Count (K-12))，勿用 Free Meal Count。"
    "Fresno Directly funded charter SAT 聚合：Charter Funding Type='Directly funded'（frpm）；"
    "TotalSchools=COUNT(DISTINCT CDSCode)；测试人数分桶 <=50、(50,100]、(100,250]；"
    "AvgFRPMPercentage=ROUND(AVG(Percent FRPM)*100,2)；SchoolAge 用 anchor 年份减 OpenDate 年。"
    "LA 低 free meal 率：FreePercent=Free Meal Count/Enrollment×100，过滤 <0.18（百分点）；"
    "CountyRank 用 ROW_NUMBER()；FreeCategory 按 FreePercent 分 Very Low/Low/Medium/High；PctLowFree 带 % 后缀。"
    "SAT excellence>30%：excellence_rate=NumGE1500/NumTstTakr（勿用总分/2400）；"
    "县内最高 free meal 用 Ages 5-17 列；school_type=Charter/Non-Charter School；"
    "free_meal_category 用 High/Medium/Low Free Meal Rate；StatusType='Active'。"
    "Top-3 SAT excellence：excellence=NumGE1500/NumTstTakr，RANK() 得 rank，WHERE rank<=3；"
    "Poverty Rate/Category 用 Percent FRPM 小数与 High/Medium/Low/Very Low Poverty。"
    "最高 Math SAT 活跃校：RANK() 得 MathRank=1；NumTstTakr>=10、StatusType Active；"
    "frpm Academic Year='2014-2015'；IsCharter 用 Y/N；% FRPM=ROUND(Percent FRPM*100,2)||'%'。"
    "Amador 高中统计：Low/High Grade='9'/'12'；Charter 用 frpm Y/N；"
    "AvgFRPM=AVG(Percent FRPM)*100；HighPoverty 用 PovertyLevel='High Poverty'；"
    "LargestSchool 用 EnrollmentRank=1。"
    "第10/11大 K-12 校：ROW_NUMBER() 得 EnrollmentRank，WHERE IN (10,11)；"
    "EligibleFreeRate=ROUND(Free/Enrollment*100,2)||'%'；SchoolType=Charter School/Regular School；"
    "PercentAbove1500SAT=COALESCE(ROUND(PercentAbove1500*100,2),0)||'%'。"
    "Ricci Ulrich 管理员校：AdmFName1='Ricci' AND AdmLName1='Ulrich'；"
    "WriteScoreRank/TotalScoreRank 用 RANK()；Comparison 文案 Equal to District Average；"
    "DifferenceFromDistrictAvg=ROUND(写分-学区均值,2)；PercentageTakingSAT=NumTstTakr×100/Enrollment(K-12)。"
    "Adelanto 最常见 GSserved：City='Adelanto'、StatusType Active；"
    "RANK() 得 grade_span_rank=1；poverty 分档用 FRPM 小数 >0.75/>0.50（勿用 75/50）。"
    "Hickman 小学区 charter：DOC='52'、Charter=1、StatusType Active、City='Hickman'；"
    "FRPMCount/FRPMPercent 用 FRPM Count 与 Percent FRPM 列；SizeRank=ROW_NUMBER() PARTITION BY City；"
    "SAT rtype='S'；SATPerformanceCategory 用 PercentOver1500 分档 High/Average/Low Performing。"
    "Sokolov 女 client（1950 前出生）：district.A2='Sokolov'（不是 A3）；disp.type OWNER；"
    "开户年龄=开户年−出生年；good loan=status'A'，in debt=status'D'（勿用 C/B 通用口径）。"
    "1994-03-03 发卡 client：cd.issued 过滤；age_at_card_issue=发卡年−出生年（勿 JULIANDAY）；"
    "avg_salary=district.A11；active_loans 计 status'A'；borrower 用 loan_count 与 Young/Mature borrower。"
    "女 client 区县 Top3 薪资：DistrictStats 按 district GROUP BY 女 client；"
    "RANK() salary_rank_in_region<=3；AccountActivity 按 account.district_id；"
    "loan 计数 A=active/B=completed/C=defaulted；regions_represented=GROUP_CONCAT(DISTINCT region)。"
    "1994-08-25 贷款：loan.date 过滤；DistrictInfo 用 RANK() 得 salary/unemployment rank（勿用 A13/A14）；"
    "avg_client_age 以贷款日 JULIANDAY；total_income_before_loan 仅 trans.type='PRIJEM'。"
    "1996-10-21 发卡最大交易：TransactionStats RANK() amount_rank=1；"
    "transaction_category=High/Medium/Low Value；loan_status Has/No Loan；district 用 client.district_id。"
    "Litomerice 1996 开户：district.A2='Litomerice'（非 A3）；ClientInfo 全 disp；"
    "1996 交易 PRIJEM/VYDAJ；avg_client_age 以 1996 年；季度占比 AVG(CASE month)%。"
    "1976-01-29 女 client：residence/account_district 用 A2 县名；"
    "district_comparison Same as residence；trans PRIJEM/VYDAJ；区县指标 JOIN A2。"
    "98832@1996-01-03 贷款：loan.date+amount 精确匹配；disp OWNER；"
    "age_at_loan 用贷款日 strftime 年差；trans 仅 date<loan_date 且 PRIJEM/VYDAJ；"
    "expense_to_income=expense/income×100；previous_loans 按 client 全部账户。"
    "south Bohemia 最多人口区县：CAST(A4 AS INTEGER)；RANK population_rank=1；"
    "total_clients=COUNT(DISTINCT client_id)。"
    "loan_id 4990：status A Running-OK、B Running-Issues、C Finished-No Issues、D Finished-Issues；"
    "problematic=B+D；"
    "district_loan_rank=RANK()；borrower 经 disp OWNER。"
    "satscores 校级 NumTstTakr/NumGE1500/Enrollment 等聚合须 rtype='S'（勿用 district/county 级 rtype）。"
)
_GENERIC_SHAPE = (
    "问句中的分组维度必须出现在最终 SELECT 和 GROUP BY 中，不能只写在 WHERE。"
    "年份若既是过滤又是汇总轴，也要投影出来。度量要聚合，排序要求要写 ORDER BY。"
    + _GENERIC_SHAPE_TAIL
)
_GENERIC_SHAPE_SQLITE = (
    "投影列必须覆盖问句与冻结契约；仅在 SQL 出现 SUM/COUNT/AVG 等聚合时写 GROUP BY，"
    "明细行或 Top-1/Top-N（LIMIT 1 或 ROW_NUMBER=1）不要对非聚合列写 GROUP BY。"
    "年份若既是过滤又是汇总轴，也要投影出来。有过滤又有聚合时度量要聚合；问句要求排序时写 ORDER BY。"
    + _GENERIC_SHAPE_TAIL
)
_POSTGRES_JOIN = (
    " 事实表与维表优先用 *_sk 连接键；先按业务键聚合再 JOIN，避免无关桥表造成笛卡尔积。"
)
SQLITE_SYSTEM_PROMPT = (
    "你是 SQLite 只读 SQL 生成器。只输出一条 SELECT 或 WITH ... SELECT，"
    "不要解释，不要写入数据，不要使用未给出的工具。"
    "表名和列名必须与可用表中的写法一致；包含空格、括号或百分号时使用双引号。"
    "可以使用 julianday、strftime、group_concat 这些 SQLite 只读函数。"
)


def system_prompt_for(*, dialect: str, profile: str) -> str:
    """电商问数继续使用原来的 PostgreSQL 系统提示。"""

    if profile == "ecommerce":
        return SYSTEM_PROMPT
    if dialect == "sqlite":
        return f"{SQLITE_SYSTEM_PROMPT}{_GENERIC_SHAPE_SQLITE}"
    return f"{SYSTEM_PROMPT}{_GENERIC_SHAPE}{_POSTGRES_JOIN}"


_FENCE = re.compile(r"```(?:sql|postgresql)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)


def extract_sql(content: str) -> str:
    """从模型输出中取出 SQL。没有代码块时使用整段文本。"""

    match = _FENCE.search(content)
    body = match.group(1) if match else content
    return body.strip()


def render_generation_prompt(
    *,
    question: str,
    schema_context: str,
    tools: Sequence[ToolHit],
    contract: AnswerContract | None = None,
    plan: str | None = None,
    output_shape: str | None = None,
) -> str:
    """组装首轮上下文。Schema 文本由调用方保证不超过预算。"""

    return _render(
        question=question,
        schema_context=schema_context,
        tools=tools,
        contract=contract,
        plan=plan,
        output_shape=output_shape,
        repair=None,
    )


def render_repair_prompt(
    *,
    question: str,
    schema_context: str,
    tools: Sequence[ToolHit],
    previous_sql: str,
    error_category: str,
    error_message: str,
    contract: AnswerContract | None = None,
    plan: str | None = None,
    output_shape: str | None = None,
) -> str:
    """把结构化错误附到下一轮。不附带原始异常。"""

    return _render(
        question=question,
        schema_context=schema_context,
        tools=tools,
        contract=contract,
        plan=plan,
        output_shape=output_shape,
        repair=(previous_sql, error_category, error_message),
    )


def _render(
    *,
    question: str,
    schema_context: str,
    tools: Sequence[ToolHit],
    contract: AnswerContract | None,
    plan: str | None,
    output_shape: str | None,
    repair: tuple[str, str, str] | None,
) -> str:
    tool_lines = [
        json.dumps(
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        for tool in tools
    ]
    sections = [f"问题：\n{question}"]
    if contract is not None:
        sections.append(format_answer_contract(contract))
    if plan:
        sections.append(plan)
    if output_shape:
        sections.append(output_shape)
    sections.extend(
        (
            f"可用表：\n{schema_context}",
            "已选择的工具定义：\n" + ("\n".join(tool_lines) if tool_lines else "无"),
        )
    )
    if repair is not None:
        previous_sql, category, message = repair
        sections.append(
            "\n".join(
                (
                    "上一次 SQL：",
                    previous_sql,
                    "结构化错误：",
                    f"category: {category}",
                    f"message: {message}",
                    "请修复为一条只读 SQL。",
                )
            )
        )
    return "\n\n".join(sections)
