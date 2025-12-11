from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Callable, Iterable, List, Optional


class StationType(Enum):
    BRANCH = "branch"  # 末端网点
    HUB = "hub"        # 分拨/中转中心
    TRANSIT = "transit"  # 干线中转站


class WaybillStatus(Enum):
    CREATED = "created"
    PICKED_UP = "picked_up"
    SORTED = "sorted"
    IN_TRANSIT = "in_transit"
    ARRIVED_HUB = "arrived_hub"
    SORTED_FOR_NEXT_LEG = "sorted_for_next_leg"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    RETURNED = "returned"
    ROUTE_ADJUSTED = "route_adjusted"
    SORTING_EXCEPTION = "sorting_exception"
    DELIVERY_EXCEPTION = "delivery_exception"


class ParcelStatus(Enum):
    CREATED = "created"
    PICKED_UP = "picked_up"
    SORTED = "sorted"
    IN_TRANSIT = "in_transit"
    AT_HUB = "at_hub"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    RETURNED = "returned"
    EXCEPTION = "exception"


class TransportTaskStatus(Enum):
    PENDING = "pending"
    LOADED = "loaded"
    IN_TRANSIT = "in_transit"
    ARRIVED = "arrived"
    CANCELLED = "cancelled"


class DispatchTaskStatus(Enum):
    READY = "ready"
    OUT_FOR_DELIVERY = "out_for_delivery"
    COMPLETED = "completed"
    FAILED = "failed"
    RETURNING = "returning"


class ExceptionType(Enum):
    SORTING = "sorting"
    ROUTE_CHANGE = "route_change"
    DELIVERY = "delivery"


class ExceptionStatus(Enum):
    OPEN = "open"
    RESOLVED = "resolved"


@dataclass
class CustomerInfo:
    name: str
    phone: str
    address: str


@dataclass
class Station:
    code: str
    name: str
    type: StationType


@dataclass
class RouteLeg:
    seq: int
    origin: Station
    destination: Station
    eta: Optional[datetime] = None


@dataclass
class RoutePlan:
    plan_id: str
    legs: List[RouteLeg]
    status: str = "planned"

    def is_last_leg(self, leg: RouteLeg) -> bool:
        return leg.seq == max((l.seq for l in self.legs), default=leg.seq)


@dataclass
class Vehicle:
    plate_no: str
    capacity: float  # 简化为重量容量


@dataclass
class Driver:
    driver_id: str
    name: str


@dataclass
class Courier:
    courier_id: str
    name: str


@dataclass
class Parcel:
    parcel_id: str
    weight: float
    size: str
    status: ParcelStatus = ParcelStatus.CREATED


@dataclass
class TrackingEvent:
    timestamp: datetime
    location: Station
    type: str
    remark: str = ""


@dataclass
class ExceptionCase:
    case_id: str
    type: ExceptionType
    status: ExceptionStatus = ExceptionStatus.OPEN
    description: str = ""
    action: str = ""


@dataclass
class TransportTask:
    task_id: str
    leg: RouteLeg
    parcels: List[Parcel]
    status: TransportTaskStatus = TransportTaskStatus.PENDING
    vehicle: Optional[Vehicle] = None
    driver: Optional[Driver] = None


@dataclass
class DispatchTask:
    task_id: str
    station: Station
    courier: Courier
    parcels: List[Parcel]
    status: DispatchTaskStatus = DispatchTaskStatus.READY
    attempt_count: int = 0


@dataclass
class Waybill:
    waybill_no: str
    sender: CustomerInfo
    receiver: CustomerInfo
    parcels: List[Parcel]
    route_plan: Optional[RoutePlan] = None
    status: WaybillStatus = WaybillStatus.CREATED
    tracking: List[TrackingEvent] = field(default_factory=list)
    exceptions: List[ExceptionCase] = field(default_factory=list)

    def add_event(self, station: Station, event_type: str, remark: str = "", now: Optional[Callable[[], datetime]] = None) -> None:
        clock = now or datetime.utcnow
        self.tracking.append(TrackingEvent(timestamp=clock(), location=station, type=event_type, remark=remark))

    def latest_location(self) -> Optional[Station]:
        if not self.tracking:
            return None
        return self.tracking[-1].location

    def apply_status_to_parcels(self, status: ParcelStatus) -> None:
        for p in self.parcels:
            p.status = status

    def open_exception(self, case: ExceptionCase) -> None:
        self.exceptions.append(case)
        self.status = {
            ExceptionType.SORTING: WaybillStatus.SORTING_EXCEPTION,
            ExceptionType.ROUTE_CHANGE: WaybillStatus.ROUTE_ADJUSTED,
            ExceptionType.DELIVERY: WaybillStatus.DELIVERY_EXCEPTION,
        }[case.type]

    def resolve_exception(self, case_id: str) -> None:
        for c in self.exceptions:
            if c.case_id == case_id:
                c.status = ExceptionStatus.RESOLVED
                break


class DomainError(Exception):
    pass


class StateTransitionError(DomainError):
    pass
