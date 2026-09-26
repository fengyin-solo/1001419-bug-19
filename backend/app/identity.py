"""经办人身份：从请求头识别当前登录的值班人员与所属班组。

平台暂不涉及完整登录体系，前端切换岗位后会把人员/班组放进请求头；
业务侧只认这里解析出来的身份，绝不采信提交体里自带的经办人字段，
避免出现“别人操作、痕迹记在我头上”的情况。
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Header

# 可以承接隧道设施的养护班组名册；名册之外的岗位（如监控值班岗）只能查看。
CREW_TEAMS = ("隧道养护一班", "隧道养护二班", "隧道养护三班")

# 未显式切换岗位时的默认身份：监控值班岗，只读，不能改动任何隧道。
DEFAULT_OPERATOR = "值班管理员"
DEFAULT_TEAM = "监控值班岗"


@dataclass(frozen=True)
class Operator:
    """一次请求携带的经办人身份。"""

    name: str
    team: str

    @property
    def is_crew(self) -> bool:
        """是否属于可承接隧道设施的养护班组。"""
        return self.team in CREW_TEAMS


def current_operator(
    x_operator_name: str = Header(default=DEFAULT_OPERATOR, alias="X-Operator-Name"),
    x_operator_team: str = Header(default=DEFAULT_TEAM, alias="X-Operator-Team"),
) -> Operator:
    """从请求头解析经办人；缺省按只读的监控值班岗处理。"""
    name = (x_operator_name or "").strip() or DEFAULT_OPERATOR
    team = (x_operator_team or "").strip() or DEFAULT_TEAM
    return Operator(name=name, team=team)
