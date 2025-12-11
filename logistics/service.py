from __future__ import annotations

from datetime import datetime
from typing import Callable, Iterable, Optional

from .models import (
    Courier,
    DispatchTask,
    DispatchTaskStatus,
    DomainError,
    Driver,
    ExceptionCase,
    ExceptionStatus,
    ExceptionType,
    Parcel,
    ParcelStatus,
    RouteLeg,
    RoutePlan,
    StateTransitionError,
    Station,
    StationType,
    TransportTask,
    TransportTaskStatus,
    Vehicle,
    Waybill,
    WaybillStatus,
)


class LogisticsService:
    """Minimal domain service to drive core flows and keep state transitions safe."""

    def __init__(self, clock: Optional[Callable[[], datetime]] = None) -> None:
        self._clock = clock or datetime.utcnow

    def pickup(self, waybill: Waybill, station: Station) -> None:
        self._ensure_status(waybill, {WaybillStatus.CREATED})
        waybill.status = WaybillStatus.PICKED_UP
        waybill.apply_status_to_parcels(ParcelStatus.PICKED_UP)
        waybill.add_event(station, "picked_up", now=self._clock)

    def sort_at(self, waybill: Waybill, station: Station) -> None:
        self._ensure_status(waybill, {WaybillStatus.PICKED_UP, WaybillStatus.ROUTE_ADJUSTED, WaybillStatus.SORTING_EXCEPTION})
        waybill.status = WaybillStatus.SORTED
        waybill.apply_status_to_parcels(ParcelStatus.SORTED)
        waybill.add_event(station, "sorted", now=self._clock)

    def create_transport_task(
        self,
        waybill: Waybill,
        leg: RouteLeg,
        vehicle: Optional[Vehicle] = None,
        driver: Optional[Driver] = None,
    ) -> TransportTask:
        return TransportTask(
            task_id=f"T-{waybill.waybill_no}-{leg.seq}",
            leg=leg,
            parcels=list(waybill.parcels),
            vehicle=vehicle,
            driver=driver,
        )

    def load_transport(self, task: TransportTask) -> None:
        if task.status not in {TransportTaskStatus.PENDING}:
            raise DomainError("任务已装载或在途")
        task.status = TransportTaskStatus.LOADED

    def depart_transport(self, waybill: Waybill, task: TransportTask) -> None:
        self._ensure_status(waybill, {WaybillStatus.SORTED, WaybillStatus.SORTED_FOR_NEXT_LEG, WaybillStatus.ROUTE_ADJUSTED})
        if task.status not in {TransportTaskStatus.LOADED, TransportTaskStatus.PENDING}:
            raise DomainError("运输任务未处于可发车状态")
        task.status = TransportTaskStatus.IN_TRANSIT
        waybill.status = WaybillStatus.IN_TRANSIT
        waybill.apply_status_to_parcels(ParcelStatus.IN_TRANSIT)
        waybill.add_event(task.leg.origin, "depart", f"to {task.leg.destination.code}", now=self._clock)

    def arrive_transport(self, waybill: Waybill, task: TransportTask) -> None:
        if task.status != TransportTaskStatus.IN_TRANSIT:
            raise DomainError("运输任务未在运输中")
        task.status = TransportTaskStatus.ARRIVED
        waybill.status = WaybillStatus.ARRIVED_HUB
        waybill.apply_status_to_parcels(ParcelStatus.AT_HUB)
        waybill.add_event(task.leg.destination, "arrive_hub", now=self._clock)

    def sort_for_next_leg(self, waybill: Waybill, station: Station) -> None:
        self._ensure_status(waybill, {WaybillStatus.ARRIVED_HUB, WaybillStatus.SORTED})
        waybill.status = WaybillStatus.SORTED_FOR_NEXT_LEG
        waybill.apply_status_to_parcels(ParcelStatus.AT_HUB)
        waybill.add_event(station, "sorted_next_leg", now=self._clock)

    def mark_out_for_delivery(self, waybill: Waybill, station: Station) -> None:
        self._ensure_status(waybill, {WaybillStatus.ARRIVED_HUB, WaybillStatus.SORTED_FOR_NEXT_LEG, WaybillStatus.OUT_FOR_DELIVERY})
        waybill.status = WaybillStatus.OUT_FOR_DELIVERY
        waybill.apply_status_to_parcels(ParcelStatus.OUT_FOR_DELIVERY)
        waybill.add_event(station, "out_for_delivery", now=self._clock)

    def create_dispatch_task(self, waybill: Waybill, station: Station, courier: Courier) -> DispatchTask:
        self.mark_out_for_delivery(waybill, station)
        return DispatchTask(task_id=f"D-{waybill.waybill_no}", station=station, courier=courier, parcels=list(waybill.parcels))

    def start_delivery(self, dispatch_task: DispatchTask) -> None:
        if dispatch_task.status != DispatchTaskStatus.READY:
            raise DomainError("派送任务不在待派送状态")
        dispatch_task.status = DispatchTaskStatus.OUT_FOR_DELIVERY

    def complete_delivery(self, waybill: Waybill, dispatch_task: DispatchTask, station: Station, remark: str = "") -> None:
        if dispatch_task.status not in {DispatchTaskStatus.READY, DispatchTaskStatus.OUT_FOR_DELIVERY}:
            raise DomainError("派送任务不在可签收状态")
        dispatch_task.status = DispatchTaskStatus.COMPLETED
        waybill.status = WaybillStatus.DELIVERED
        waybill.apply_status_to_parcels(ParcelStatus.DELIVERED)
        waybill.add_event(station, "delivered", remark, now=self._clock)

    def record_sorting_exception(self, waybill: Waybill, station: Station, case_id: str, description: str) -> ExceptionCase:
        self._ensure_status(waybill, {WaybillStatus.SORTED, WaybillStatus.ARRIVED_HUB})
        case = ExceptionCase(case_id=case_id, type=ExceptionType.SORTING, description=description)
        waybill.open_exception(case)
        waybill.apply_status_to_parcels(ParcelStatus.EXCEPTION)
        waybill.add_event(station, "sorting_exception", description, now=self._clock)
        return case

    def record_route_adjustment(self, waybill: Waybill, station: Station, case_id: str, new_plan: RoutePlan, remark: str = "") -> ExceptionCase:
        self._ensure_status(waybill, {WaybillStatus.IN_TRANSIT})
        case = ExceptionCase(case_id=case_id, type=ExceptionType.ROUTE_CHANGE, description=remark)
        waybill.route_plan = new_plan
        waybill.open_exception(case)
        waybill.add_event(station, "route_adjusted", remark, now=self._clock)
        return case

    def record_delivery_exception(self, waybill: Waybill, station: Station, dispatch_task: DispatchTask, case_id: str, description: str) -> ExceptionCase:
        case = ExceptionCase(case_id=case_id, type=ExceptionType.DELIVERY, description=description)
        dispatch_task.status = DispatchTaskStatus.FAILED
        waybill.open_exception(case)
        waybill.apply_status_to_parcels(ParcelStatus.EXCEPTION)
        waybill.add_event(station, "delivery_exception", description, now=self._clock)
        return case

    def resolve_exception(self, waybill: Waybill, case_id: str, target_status: WaybillStatus, remark: str = "") -> None:
        waybill.resolve_exception(case_id)
        waybill.status = target_status
        if target_status == WaybillStatus.SORTED:
            waybill.apply_status_to_parcels(ParcelStatus.SORTED)
        elif target_status == WaybillStatus.OUT_FOR_DELIVERY:
            waybill.apply_status_to_parcels(ParcelStatus.OUT_FOR_DELIVERY)
        waybill.add_event(waybill.latest_location() or Station("unknown", "unknown", StationType.TRANSIT), "exception_resolved", remark, now=self._clock)

    def _ensure_status(self, waybill: Waybill, allowed: Iterable[WaybillStatus]) -> None:
        if waybill.status not in set(allowed):
            allowed_names = ", ".join(s.value for s in allowed)
            raise StateTransitionError(f"当前状态 {waybill.status.value} 不允许该操作，期望: {allowed_names}")
