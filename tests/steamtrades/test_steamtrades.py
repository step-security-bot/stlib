import configparser
import os

import aiohttp
import pytest
from stlib import authenticator, steamtrades, webapi

from tests import MANUAL_TESTING, debug, requires_manual_testing


class TestSteamTrades:
    if MANUAL_TESTING:
        config_parser = configparser.RawConfigParser()
        config_parser.read(os.path.join(os.path.dirname(__file__), '..', 'conftest.ini'))
        trade_id = config_parser.get("Test", "trade_id")
        nickname = config_parser.get("Test", "nickname")
        username = config_parser.get("Test", "username")
        password = config_parser.get("Test", "password")
        adb_path = config_parser.get("Test", "adb_path")
        adb = authenticator.AndroidDebugBridge(adb_path)

    @pytest.mark.asyncio
    async def test_get_trade_info(self):
        async with aiohttp.ClientSession(raise_for_status=True) as session:
            http = steamtrades.Http(session)
            trade_info = await http.get_trade_info(self.trade_id)

        assert isinstance(trade_info.id, str)
        assert len(trade_info.id) == 5
        assert isinstance(trade_info.title, str)
        assert isinstance(trade_info.html, str)
        assert f'/trade/{self.trade_id}' in trade_info.html

    @requires_manual_testing
    @pytest.mark.asyncio
    async def test_bump(self):
        async with aiohttp.ClientSession(raise_for_status=True) as session:
            http = webapi.Http(session, 'https://lara.click/api')
            steam_key = await http.get_steam_key(self.username)
            encrypted_password = webapi.encrypt_password(steam_key, self.password.encode())
            json_data = await self.adb.get_json('shared_secret')
            debug(str(json_data))
            code = authenticator.get_code(json_data['shared_secret'])

            json_data = await http.do_login('laracraft93', encrypted_password, steam_key.timestamp, code.code)
            debug(str(json_data))
            assert isinstance(json_data['success'], bool)
            assert json_data['success'] == True

            json_data = await http.do_openid_login('https://steamtrades.com/?login')
            debug(str(json_data))
            assert isinstance(json_data['success'], bool)
            assert json_data['success'] == True

            http = steamtrades.Http(session)
            trade_info = await http.get_trade_info(self.trade_id)
            #bump_result = await http.bump(trade_info)
            #debug(str(bump_result))
            #assert isinstance(bump_result, bool)
