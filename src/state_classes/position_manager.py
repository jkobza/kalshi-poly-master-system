import uuid

from state_classes.arb_holder import MarketHolder
from src.state_classes.order import Order
from src.state_classes.position import Position
from typing import Optional
from src.util.enums import OrderSide, OrderStatus, Exchange, PositionStatus


class PositionManager:



    def __init__(self, market_holder: MarketHolder, kalshi_balance, poly_balance):
        """
        Initialize position stores, balance snapshots, active asset tracking, and lookup maps.
        """
        self.open_positions = {}
        self.closed_positions = []
        self.kalshi_balance = kalshi_balance
        self.poly_balance = poly_balance
        self.active_ids = set()
        # Mapping lookups
        self.orderid_to_pos_id = {}
        self.assetid_to_pos_id = {}
        self.market = market_holder

    def add_position(self, position: Position):
        """
        Add an open position and index it by asset IDs and any available entry-leg order IDs.
        :param position: the position to be added
        """
        self.open_positions[position.pos_id] = position

        # Map asset IDs to the position
        self.assetid_to_pos_id[position.kalshi_id] = position.pos_id
        self.assetid_to_pos_id[position.poly_id] = position.pos_id

        # Map existing entry leg order IDs
        for leg in [position.entry_leg_kalshi, position.entry_leg_poly]:
            if leg:
                self.orderid_to_pos_id[leg.internal_order_id] = position.pos_id

    def get_position_by_order(self, order_id: int) -> Optional[Position]:
        """
        Look up an open position by an internal order ID, returning None when no mapping exists.
        """
        pos_id = self.orderid_to_pos_id.get(order_id)
        return self.open_positions.get(pos_id)

    def get_position_by_asset(self, asset_id: str) -> Optional[Position]:
        """
        Look up an open position by either exchange asset ID, returning None when no mapping exists.
        """
        pos_id = self.assetid_to_pos_id.get(asset_id)
        return self.open_positions.get(pos_id)

    def add_closing_order(self, position: Position, order: 'Order'):
        """Links an exit order to a position and updates the mapping."""
        self.orderid_to_pos_id[order.internal_order_id] = position.pos_id

        if order.exchange == Exchange.KALSHI:
            position.exit_leg_kalshi = order
        elif order.exchange == Exchange.POLYMARKET:
            position.exit_leg_poly = order

    def update_and_check_close(self, position: Position):
        """Moves position to closed if both exit legs are filled."""
        k_filled = position.exit_leg_kalshi and position.exit_leg_kalshi.status == OrderStatus.FILLED
        p_filled = position.exit_leg_poly and position.exit_leg_poly.status == OrderStatus.FILLED

        if k_filled and p_filled:
            # Cleanup mappings to prevent memory leaks
            self._cleanup_position_mappings(position)
            del self.open_positions[position.pos_id]
            self.closed_positions.append(position)
            position.status = PositionStatus.CLOSED

    def _cleanup_position_mappings(self, position: Position):
        """Removes IDs from lookup dictionaries to keep them lean."""
        ids_to_remove = [position.kalshi_id, position.poly_id]
        for aid in ids_to_remove:
            self.assetid_to_pos_id.pop(aid, None)

        # Clean up all possible order legs
        legs = [position.entry_leg_kalshi, position.entry_leg_poly,
                position.exit_leg_kalshi, position.exit_leg_poly]
        for leg in legs:
            if leg:
                self.orderid_to_pos_id.pop(leg.internal_order_id, None)

    def has_open_position_for_asset(self, asset_id: str) -> bool:
        """
        Return True when an asset ID is already associated with an open position.
        """
        return asset_id in self.assetid_to_pos_id




