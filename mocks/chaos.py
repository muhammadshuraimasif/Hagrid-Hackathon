"""
Chaos engineering failure injection controller for mock services.
PROTOTYPE ONLY.
Supports: latency injection, 500 internal errors, simulated timeouts, and stale data.
"""
import asyncio
from typing import Dict, Any, Optional
from fastapi import HTTPException, status

class ChaosController:
    def __init__(self):
        self.reset()

    def reset(self):
        self._state: Dict[str, Dict[str, Any]] = {
            "nadra": {
                "latency_ms": 0,
                "error_500": False,
                "timeout": False,
                "stale_data": False
            },
            "raast": {
                "latency_ms": 0,
                "error_500": False,
                "timeout": False
            },
            "sms": {
                "latency_ms": 0,
                "error_500": False
            }
        }

    def get_state(self) -> Dict[str, Dict[str, Any]]:
        return self._state

    def update_service_chaos(self, service: str, **kwargs) -> Dict[str, Any]:
        if service not in self._state:
            self._state[service] = {}
        for k, v in kwargs.items():
            if v is not None:
                self._state[service][k] = v
        return self._state[service]

    async def apply_chaos(self, service: str) -> bool:
        """
        Executes configured chaos rules for a service.
        Returns whether 'stale_data' mode is active.
        """
        cfg = self._state.get(service, {})
        
        # 1. Timeout injection
        if cfg.get("timeout"):
            # Sleep longer than the client's timeout (client default is 2-3s)
            await asyncio.sleep(5.0)
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail={"code": "CHAOS_TIMEOUT", "message": f"Simulated gateway timeout for {service}"}
            )

        # 2. 500 error injection
        if cfg.get("error_500"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"code": "CHAOS_500", "message": f"Simulated 500 internal error for {service}"}
            )

        # 3. Latency injection
        latency = cfg.get("latency_ms", 0)
        if latency > 0:
            await asyncio.sleep(latency / 1000.0)

        # 4. Return stale_data flag
        return bool(cfg.get("stale_data", False))

chaos_controller = ChaosController()
