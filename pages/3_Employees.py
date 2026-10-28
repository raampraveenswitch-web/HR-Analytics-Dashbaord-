import pandas as pd
import streamlit as st

from services import metrics as M
from services import ui
from services.insights import employee_insights

store = ui.page_setup("Employees", "Workforce Overview", "👥")
ui.gate(store, ["Total employees", "New hires", "Employee exits", "Attrition rate", "Average tenure",
                "Engagement score"], needs=("employee",))
ctx = ui.context(store)
e = ui.filters(ctx.ds["employee"], {"department": "Department", "function": "Function",
                                     "employee_type": "Employee type", "level": "Level", "gender": "Gender"}, "emp")
on = ctx.asof()
rel = ctx.ds.get("relations")

ui.kpi_cards([
    ctx.cmp(lambda q: M.emp_headcount(e, ctx.asof(q))), ctx.cmp(lambda q: M.emp_new_hires(e, q)),
    ctx.cmp(lambda q: M.emp_exits(e, q)), ctx.cmp(lambda q: M.emp_attrition(e, q)),
    ctx.cmp(lambda q: M.emp_tenure(e, ctx.asof(q))),
    ctx.static("relations", "Engagement score", "score", lambda q: M.rel_engagement(rel))])

# ---- trend · donut · tenure · focus ------------------------------------------
a, b, c, d = ui.row()
bx = ui.panel(a, "Headcount Trend", "Joiners and leavers by month, with month-end headcount")
hc = M.emp_headcount_trend(e, ctx.window) if ctx.window else None
parts = []
if "hire_date" in e.columns:
    h = e[e["hire_date"].notna()]
    parts.append(h.groupby(h["hire_date"].dt.to_period("M")).size().rename("Joiners"))
if "exit_date" in e.columns and e["exit_date"].notna().any():
    x = e[e["exit_date"].notna()]
    parts.append(x.groupby(x["exit_date"].dt.to_period("M")).size().rename("Leavers"))
if hc is not None and parts:
    lc = pd.concat(parts, axis=1).fillna(0)
    lc.index = lc.index.to_timestamp()
    hc = hc.assign(Month=hc["Month end"].dt.to_period("M").dt.to_timestamp())
    tr = hc.merge(lc, left_on="Month", right_index=True, how="left").fillna({"Joiners": 0, "Leavers": 0})
    ui.combo(bx, tr, "Month", [k for k in ("Joiners", "Leavers") if k in tr], line="Headcount", line_secondary=True)
else:
    ui.unavailable(bx, "date of joining not found.")

bx = ui.panel(b, "Headcount by Department", "Active employees at period end")
dd = next((x for x in (M.emp_distribution(e, k, on) for k in ("department", "function")) if x is not None), None)
ui.donut(bx, dd, dd.columns[0], "Employees", center="Employees") if dd is not None else ui.unavailable(bx, "department column not found.")

bx = ui.panel(c, "Tenure Distribution", "Active employees by tenure band")
dd = M.emp_tenure_bands(e, on)
ui.bar(bx, dd, "Tenure band", "Employees", height=300) if dd is not None else ui.unavailable(bx, "date of joining not found.")

ui.focus(ui.panel(d, "Workforce Focus Areas", icon="target"), employee_insights(e, ctx.period), "employees")

# ---- detail rows ---------------------------------------------------------------
a, b, c, d = ui.row((1, 1, 1, 1))
for holder, (title, col, kind) in zip((a, b, c, d), (("Distribution by Function", "function", "bar"),
                                                      ("Employee Type", "employee_type", "donut"),
                                                      ("Gender Mix", "gender", "donut"),
                                                      ("Level / Grade", "level", "bar"))):
    bx = ui.card(title, "Active employees at period end" + ("; small groups hidden" if col in ("gender", "level") else ""),
                    parent=holder)
    dd = M.emp_distribution(e, col, on)
    n = 0
    if col in ("gender", "level"):
        dd, n = M.small_group_filter(dd, "Employees")
    if dd is None or not len(dd):
        ui.unavailable(bx, f"{col.replace('_', ' ')} column not found or groups too small.")
    elif kind == "donut":
        ui.donut(bx, dd, dd.columns[0], "Employees", height=ui.DETAIL_CHART_H)
    else:
        ui.bar(bx, dd, "Employees", dd.columns[0], orient="h", height=ui.DETAIL_CHART_H)
    ui.suppressed_note(bx, n)

a, b = ui.row((1, 1))
ui.unavailable(ui.card("Skills and Competencies", parent=a), "no skills/competency columns are mapped for employees.")
bx = ui.card("Satisfaction & Engagement", "Average survey score (see Employee Relations for detail)", parent=b, icon="heart")
m_ = M.rel_engagement(rel) if rel is not None else None
bx.markdown(f"**{ui.fmt(m_)}**" + (f" — {m_.detail}" if m_.available else f" — {m_.reason}") if m_ else "Not available — no survey data found.")
