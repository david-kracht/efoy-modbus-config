import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import socket

from modbus_common.client import ModbusClientWrapper

@pytest.fixture
def mock_tcp_client():
    with patch("modbus_common.client.AsyncModbusTcpClient") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.connect = AsyncMock(return_value=True)
        mock_instance.close = MagicMock()
        # Mock the underlying socket for keep-alive testing
        mock_sock = MagicMock()
        mock_transport = MagicMock()
        mock_transport.get_extra_info.return_value = mock_sock
        mock_ctx = MagicMock()
        mock_ctx.transport = mock_transport
        mock_instance.ctx = mock_ctx
        
        # Initial state
        mock_instance.connected = False
        
        mock_cls.return_value = mock_instance
        yield mock_instance

@pytest.mark.anyio
async def test_client_connect_success(mock_tcp_client):
    wrapper = ModbusClientWrapper(host="127.0.0.1", port=502)
    assert not wrapper.connected
    
    # Simulate pymodbus setting connected = True after a slight delay during connection
    async def side_effect():
        mock_tcp_client.connected = True
        return True
    
    mock_tcp_client.connect.side_effect = side_effect
    
    success = await wrapper.connect()
    assert success is True
    assert wrapper.connected is True
    mock_tcp_client.connect.assert_called_once()

@pytest.mark.anyio
async def test_client_connect_failure(mock_tcp_client):
    wrapper = ModbusClientWrapper(host="127.0.0.1", port=502)
    
    # Simulate connection failure
    mock_tcp_client.connect.return_value = False
    mock_tcp_client.connected = False
    
    success = await wrapper.connect()
    assert success is False
    assert wrapper.connected is False

@pytest.mark.anyio
async def test_client_keepalive_applied(mock_tcp_client):
    wrapper = ModbusClientWrapper(host="127.0.0.1", port=502)
    
    async def side_effect():
        mock_tcp_client.connected = True
        return True
    
    mock_tcp_client.connect.side_effect = side_effect
    
    await wrapper.connect()
    
    mock_sock = mock_tcp_client.ctx.transport.get_extra_info.return_value
    mock_sock.setsockopt.assert_any_call(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

@pytest.mark.anyio
async def test_client_close(mock_tcp_client):
    wrapper = ModbusClientWrapper(host="127.0.0.1", port=502)
    
    async def side_effect():
        mock_tcp_client.connected = True
        return True
    mock_tcp_client.connect.side_effect = side_effect
    
    await wrapper.connect()
    assert wrapper.connected is True
    
    await wrapper.close()
    assert wrapper.connected is False
    assert wrapper.client is None
    mock_tcp_client.close.assert_called_once()

@pytest.mark.anyio
async def test_client_connect_already_connected(mock_tcp_client):
    wrapper = ModbusClientWrapper(host="127.0.0.1", port=502)
    
    async def side_effect():
        mock_tcp_client.connected = True
        return True
    mock_tcp_client.connect.side_effect = side_effect
    
    await wrapper.connect()
    assert mock_tcp_client.connect.call_count == 1
    
    # Connect again should be a no-op
    await wrapper.connect()
    assert mock_tcp_client.connect.call_count == 1
