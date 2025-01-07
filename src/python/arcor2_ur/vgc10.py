import pymodbus.client as ModbusClient
from pymodbus import ExceptionResponse, FramerType, ModbusException, pymodbus_apply_logging_config

from arcor2 import env
from arcor2.exceptions import Arcor2Exception

if env.get_bool("ARCOR2_UR_MODBUS_DEBUG", False):
    pymodbus_apply_logging_config("DEBUG")


class VGC10Exception(Arcor2Exception):
    pass


# adapted from https://github.com/fwarmuth/onrobot-vg/tree/feat/serial-connection


class VGC10:
    def __init__(self, ip: str, port: int) -> None:
        self._client = ModbusClient.ModbusTcpClient(
            ip,
            port=port,
            framer=FramerType.RTU,
            timeout=10,
            retries=10,
        )

    def _handle_result(self, result) -> None:
        """Deals with erroneous results."""

        if result.isError():
            self._client.close()
            raise VGC10Exception(f"Received Modbus library error({result})")
        if isinstance(result, ExceptionResponse):
            # THIS IS NOT A PYTHON EXCEPTION, but a valid modbus message
            self._client.close()
            raise VGC10Exception(f"Received Modbus library exception ({result})")

    def open_connection(self) -> None:
        """Opens the connection with a gripper."""
        self._client.connect()

    def close_connection(self) -> None:
        """Closes the connection with the gripper."""
        self._client.close()

    def get_vacuum_limit(self) -> int:
        """Sets and reads the current limit.

        The limit is provided and must be given in mA (milli-amperes).
        The limit is 500mA per default and should never be set above
        1000 mA.
        """
        try:
            result = self._client.read_holding_registers(address=2, count=1, slave=65)
        except ModbusException as exc:
            raise VGC10Exception(f"Exception on modbus communication. {exc}")
        self._handle_result(result)
        limit_mA = result.registers[0]
        return limit_mA

    def get_channelA_vacuum(self) -> float:
        """Reads the actual vacuum on Channel A.

        The vacuum is provided in 1/1000 of relative vacuum. Please note
        that this differs from the setpoint given in percent, as extra
        accuracy is desirable on the actual vacuum.
        """
        try:
            result = self._client.read_holding_registers(address=258, count=1, slave=65)
        except ModbusException as exc:
            raise VGC10Exception(f"Exception on modbus communication. {exc}")
        self._handle_result(result)

        vacuum = result.registers[0] / 10.0
        return vacuum

    def get_channelB_vacuum(self) -> float:
        """Same as the one of channel B."""
        try:
            result = self._client.read_holding_registers(address=259, count=1, slave=65)
        except ModbusException as exc:
            raise VGC10Exception(f"Exception on modbus communication. {exc}")

        self._handle_result(result)

        vacuum = result.registers[0] / 10.0
        return vacuum

    def vacuum_on(self, vac: int = 20) -> None:
        """Turns on all vacuums."""

        if 0 > vac > 80:
            raise ValueError("Invalid value for vacuum.")

        modeval = 0x0100  # grip
        # command = 0x00ff  # 100 % vacuum
        commands: list[int] = [modeval + vac, modeval + vac]
        try:
            result = self._client.write_registers(address=0, values=commands, slave=65)
        except ModbusException as exc:
            raise VGC10Exception(f"Exception on modbus communication. {exc}")

        self._handle_result(result)

    def release_vacuum(self) -> None:
        """Releases all vacuums."""
        modeval = 0x0000  # release
        command = 0x0000  # 0 % vacuum
        commands: list[int] = [modeval + command, modeval + command]

        try:
            result = self._client.write_registers(address=0, values=commands, slave=65)
        except ModbusException as exc:
            raise VGC10Exception(f"Exception on modbus communication. {exc}")

        self._handle_result(result)
