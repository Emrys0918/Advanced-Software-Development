from __future__ import annotations

from .models import (
    Courier,
    CustomerInfo,
    Driver,
    Parcel,
    RouteLeg,
    RoutePlan,
    Station,
    StationType,
    Vehicle,
    Waybill,
    WaybillStatus,
)
from .service import LogisticsService


def build_stations():
    """构建站点网络"""
    sh_branch = Station(code="SH-B", name="Shanghai Branch", type=StationType.BRANCH)
    sh_hub = Station(code="SH-H", name="Shanghai Hub", type=StationType.HUB)
    nj_hub = Station(code="NJ-H", name="Nanjing Hub", type=StationType.HUB)
    bj_branch = Station(code="BJ-B", name="Beijing Branch", type=StationType.BRANCH)
    return sh_branch, sh_hub, nj_hub, bj_branch


def build_sample_waybill(sh_branch, sh_hub, bj_branch) -> Waybill:
    sender = CustomerInfo(name="Alice", phone="13800000000", address="Shanghai Pudong 1")
    receiver = CustomerInfo(name="Bob", phone="13900000000", address="Beijing Chaoyang 2")

    legs = [
        RouteLeg(seq=1, origin=sh_branch, destination=sh_hub),
        RouteLeg(seq=2, origin=sh_hub, destination=bj_branch),
    ]

    route_plan = RoutePlan(plan_id="RP-001", legs=legs)

    parcels = [
        Parcel(parcel_id="P1", weight=1.2, size="30x20x10"),
        Parcel(parcel_id="P2", weight=0.8, size="25x18x8"),
    ]

    return Waybill(waybill_no="WB1001", sender=sender, receiver=receiver, parcels=parcels, route_plan=route_plan)


def print_status(waybill: Waybill, title: str) -> None:
    """打印运单当前状态"""
    print(f"\n{'='*60}")
    print(f"【{title}】")
    print(f"  运单状态: {waybill.status.value}")
    print(f"  包裹状态: {[p.status.value for p in waybill.parcels]}")
    print(f"  异常记录: {len(waybill.exceptions)} 条")


def run_normal_flow() -> None:
    """演示正常流程"""
    print("\n" + "="*60)
    print("场景一：正常流程演示")
    print("="*60)

    sh_branch, sh_hub, nj_hub, bj_branch = build_stations()
    svc = LogisticsService()
    waybill = build_sample_waybill(sh_branch, sh_hub, bj_branch)

    # 创建车辆和司机
    vehicle = Vehicle(plate_no="沪A12345", capacity=1000.0)
    driver = Driver(driver_id="D01", name="Driver Wang")

    # 1. 揽收
    svc.pickup(waybill, sh_branch)
    print_status(waybill, "揽收完成")

    # 2. 分拣
    svc.sort_at(waybill, sh_branch)

    # 3. 第一段运输：上海网点 -> 上海中转
    leg1 = waybill.route_plan.legs[0]
    t1 = svc.create_transport_task(waybill, leg1, vehicle=vehicle, driver=driver)
    svc.load_transport(t1)
    svc.depart_transport(waybill, t1)
    svc.arrive_transport(waybill, t1)
    print_status(waybill, "到达上海中转站")

    # 4. 中转分拣
    svc.sort_for_next_leg(waybill, sh_hub)

    # 5. 第二段运输：上海中转 -> 北京网点
    leg2 = waybill.route_plan.legs[1]
    t2 = svc.create_transport_task(waybill, leg2, vehicle=vehicle, driver=driver)
    svc.load_transport(t2)
    svc.depart_transport(waybill, t2)
    svc.arrive_transport(waybill, t2)
    print_status(waybill, "到达目的网点")

    # 6. 派送
    courier = Courier(courier_id="C01", name="Courier Zhang")
    dispatch_task = svc.create_dispatch_task(waybill, bj_branch, courier)
    svc.start_delivery(dispatch_task)
    svc.complete_delivery(waybill, dispatch_task, bj_branch, remark="收件人签收")

    print_status(waybill, "签收完成")
    print("\n全量追踪事件:")
    for e in waybill.tracking:
        print(f"  {e.timestamp.strftime('%H:%M:%S')} | {e.location.code:6} | {e.type:18} | {e.remark}")


def run_sorting_exception_flow() -> None:
    """演示分拣异常流程"""
    print("\n" + "="*60)
    print("场景二：分拣异常处理")
    print("="*60)

    sh_branch, sh_hub, nj_hub, bj_branch = build_stations()
    svc = LogisticsService()
    waybill = build_sample_waybill(sh_branch, sh_hub, bj_branch)

    svc.pickup(waybill, sh_branch)
    svc.sort_at(waybill, sh_branch)

    # 到达中转站后发现标签损坏
    leg1 = waybill.route_plan.legs[0]
    t1 = svc.create_transport_task(waybill, leg1)
    svc.load_transport(t1)
    svc.depart_transport(waybill, t1)
    svc.arrive_transport(waybill, t1)

    # 记录分拣异常：标签损坏
    case = svc.record_sorting_exception(waybill, sh_hub, "EX-001", "标签损坏，地址不清晰")
    print_status(waybill, "分拣异常发生")

    # 联系发件人确认后解决异常
    svc.resolve_exception(waybill, case.case_id, WaybillStatus.SORTED, "已重新核实地址并补打标签")
    print_status(waybill, "异常解决，继续分拣")

    # 继续正常流程
    svc.sort_for_next_leg(waybill, sh_hub)
    leg2 = waybill.route_plan.legs[1]
    t2 = svc.create_transport_task(waybill, leg2)
    svc.load_transport(t2)
    svc.depart_transport(waybill, t2)
    svc.arrive_transport(waybill, t2)

    courier = Courier(courier_id="C01", name="Courier Zhang")
    dispatch_task = svc.create_dispatch_task(waybill, bj_branch, courier)
    svc.start_delivery(dispatch_task)
    svc.complete_delivery(waybill, dispatch_task, bj_branch)

    print_status(waybill, "最终状态")
    print(f"\n异常记录详情:")
    for ex in waybill.exceptions:
        print(f"  {ex.case_id}: {ex.type.value} - {ex.description} [{ex.status.value}]")


def run_route_change_flow() -> None:
    """演示路线变更流程"""
    print("\n" + "="*60)
    print("场景三：运输路线变更")
    print("="*60)

    sh_branch, sh_hub, nj_hub, bj_branch = build_stations()
    svc = LogisticsService()
    waybill = build_sample_waybill(sh_branch, sh_hub, bj_branch)

    svc.pickup(waybill, sh_branch)
    svc.sort_at(waybill, sh_branch)

    leg1 = waybill.route_plan.legs[0]
    t1 = svc.create_transport_task(waybill, leg1)
    svc.load_transport(t1)
    svc.depart_transport(waybill, t1)

    # 运输途中遇到天气原因，需要绕道南京
    new_legs = [
        RouteLeg(seq=1, origin=sh_branch, destination=nj_hub),
        RouteLeg(seq=2, origin=nj_hub, destination=bj_branch),
    ]
    new_plan = RoutePlan(plan_id="RP-001-REV", legs=new_legs)

    case = svc.record_route_adjustment(waybill, sh_hub, "EX-002", new_plan, "天气原因改道南京")
    print_status(waybill, "路线变更")

    # 解决异常后，到达新的中转站
    svc.resolve_exception(waybill, case.case_id, WaybillStatus.SORTED, "已按新路线调度")

    # 继续运输到目的地（使用新路线的第二段）
    leg2 = waybill.route_plan.legs[1]
    t2 = svc.create_transport_task(waybill, leg2)
    svc.load_transport(t2)
    svc.depart_transport(waybill, t2)
    svc.arrive_transport(waybill, t2)

    courier = Courier(courier_id="C02", name="Courier Li")
    dispatch_task = svc.create_dispatch_task(waybill, bj_branch, courier)
    svc.start_delivery(dispatch_task)
    svc.complete_delivery(waybill, dispatch_task, bj_branch)

    print_status(waybill, "最终状态")


def run_delivery_exception_flow() -> None:
    """演示派送异常流程（二次派送）"""
    print("\n" + "="*60)
    print("场景四：派送异常（二次派送）")
    print("="*60)

    sh_branch, sh_hub, nj_hub, bj_branch = build_stations()
    svc = LogisticsService()
    waybill = build_sample_waybill(sh_branch, sh_hub, bj_branch)

    # 快速走完运输流程
    svc.pickup(waybill, sh_branch)
    svc.sort_at(waybill, sh_branch)
    leg1 = waybill.route_plan.legs[0]
    t1 = svc.create_transport_task(waybill, leg1)
    svc.load_transport(t1)
    svc.depart_transport(waybill, t1)
    svc.arrive_transport(waybill, t1)
    svc.sort_for_next_leg(waybill, sh_hub)
    leg2 = waybill.route_plan.legs[1]
    t2 = svc.create_transport_task(waybill, leg2)
    svc.load_transport(t2)
    svc.depart_transport(waybill, t2)
    svc.arrive_transport(waybill, t2)

    # 第一次派送
    courier = Courier(courier_id="C01", name="Courier Zhang")
    dispatch_task = svc.create_dispatch_task(waybill, bj_branch, courier)
    svc.start_delivery(dispatch_task)

    # 收件人不在家，派送失败
    case = svc.record_delivery_exception(waybill, bj_branch, dispatch_task, "EX-003", "收件人不在家")
    print_status(waybill, "第一次派送失败")
    print(f"  派送任务状态: {dispatch_task.status.value}")
    print(f"  尝试次数: {dispatch_task.attempt_count}")

    # 解决异常，安排二次派送
    svc.resolve_exception(waybill, case.case_id, WaybillStatus.OUT_FOR_DELIVERY, "已联系收件人，安排二次派送")

    # 创建新的派送任务进行二次派送
    dispatch_task2 = svc.create_dispatch_task(waybill, bj_branch, courier)
    dispatch_task2.attempt_count = 1  # 标记为第二次尝试
    svc.start_delivery(dispatch_task2)
    svc.complete_delivery(waybill, dispatch_task2, bj_branch, remark="二次派送成功签收")

    print_status(waybill, "二次派送成功")


def run_demo() -> None:
    """运行所有演示场景"""
    run_normal_flow()
    run_sorting_exception_flow()
    run_route_change_flow()
    run_delivery_exception_flow()

    print("\n" + "="*60)
    print("全部场景演示完成!")
    print("="*60)


if __name__ == "__main__":
    run_demo()
