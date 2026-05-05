# -*- coding: utf-8 -*-
# This file is auto-generated, don't edit it. Thanks.
import json
import os
import sys

from typing import List

from alibabacloud_dyvmsapi20170525.client import Client as Dyvmsapi20170525Client
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_dyvmsapi20170525 import models as dyvmsapi_20170525_models
from alibabacloud_tea_util import models as util_models
from alibabacloud_tea_util.client import Client as UtilClient

from utils import logger

devicelogger = logger.getLogger('dynamic')


def send_voice_phone(data, called_number, play_times):
    client = Sample.create_client(
        os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID", ""),
        os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET", ""),
    )
    # data = {'deviceType': '烟雾报警器', 'pointName': '威富集团'}
    single_call_by_tts_request = dyvmsapi_20170525_models.SingleCallByTtsRequest(
        # called_show_number='420-8888-7777',
        # called_number='18998911296',
        called_number=str(called_number),
        tts_code='TTS_287085213',
        tts_param=json.dumps(data),
        # play_times=3,
        play_times=int(play_times),
        volume=60,
        speed=3
    )
    runtime = util_models.RuntimeOptions()
    try:
        # 复制代码运行请自行打印 API 的返回值
        response = client.single_call_by_tts_with_options(single_call_by_tts_request, runtime)
        devicelogger.info(response)
    except Exception as error:
        # 错误 message
        devicelogger.info(error.message)
        # 诊断地址
        devicelogger.info(error.data.get("Recommend"))
        UtilClient.assert_as_string(error.message)
    pass


class Sample:
    def __init__(self):
        pass

    @staticmethod
    def create_client(
            access_key_id: str,
            access_key_secret: str,
    ) -> Dyvmsapi20170525Client:
        """
        使用AK&SK初始化账号Client
        @param access_key_id:
        @param access_key_secret:
        @return: Client
        @throws Exception
        """
        config = open_api_models.Config(
            # 必填，您的 AccessKey ID,
            access_key_id=access_key_id,
            # 必填，您的 AccessKey Secret,
            access_key_secret=access_key_secret
        )
        # Endpoint 请参考 https://api.aliyun.com/product/Dyvmsapi
        # config.endpoint = f'dyvmsapi.aliyuncs.com'
        return Dyvmsapi20170525Client(config)

    @staticmethod
    def main(
            args: List[str],
    ) -> None:
        # 请确保代码运行环境设置了环境变量 ALIBABA_CLOUD_ACCESS_KEY_ID 和 ALIBABA_CLOUD_ACCESS_KEY_SECRET。
        # 工程代码泄露可能会导致 AccessKey 泄露，并威胁账号下所有资源的安全性。以下代码示例使用环境变量获取 AccessKey 的方式进行调用，仅供参考，建议使用更安全的 STS 方式，更多鉴权访问方式请参见：https://help.aliyun.com/document_detail/378659.html
        client = Sample.create_client(
            os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID", ""),
            os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET", ""),
        )
        data = {'deviceType': '烟雾报警器', 'pointName': '威富集团'}
        single_call_by_tts_request = dyvmsapi_20170525_models.SingleCallByTtsRequest(
            called_show_number='420-8888-7777',
            called_number='18998911296',
            tts_code='TTS_287085213',
            tts_param=json.dumps(data),
            play_times=3,
            volume=60,
            speed=3
        )
        runtime = util_models.RuntimeOptions()
        try:
            # 复制代码运行请自行打印 API 的返回值
            response = client.single_call_by_tts_with_options(single_call_by_tts_request, runtime)
            print(response)
        except Exception as error:
            # 错误 message
            print(error.message)
            # 诊断地址
            print(error.data.get("Recommend"))
            UtilClient.assert_as_string(error.message)

    @staticmethod
    async def main_async(
            args: List[str],
    ) -> None:
        # 请确保代码运行环境设置了环境变量 ALIBABA_CLOUD_ACCESS_KEY_ID 和 ALIBABA_CLOUD_ACCESS_KEY_SECRET。
        # 工程代码泄露可能会导致 AccessKey 泄露，并威胁账号下所有资源的安全性。以下代码示例使用环境变量获取 AccessKey 的方式进行调用，仅供参考，建议使用更安全的 STS 方式，更多鉴权访问方式请参见：https://help.aliyun.com/document_detail/378659.html
        client = Sample.create_client(
            os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID", ""),
            os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET", ""),
        )
        data = {'deviceType': '烟雾报警器', 'pointName': '威富集团'}
        single_call_by_tts_request = dyvmsapi_20170525_models.SingleCallByTtsRequest(
            called_show_number='420-8888-7777',
            called_number='18998911296',
            tts_code='TTS_287085213',
            tts_param=json.dumps(data),
            play_times=3,
            volume=60,
            speed=3
        )
        runtime = util_models.RuntimeOptions()
        try:
            # 复制代码运行请自行打印 API 的返回值
            await client.single_call_by_tts_with_options_async(single_call_by_tts_request, runtime)
        except Exception as error:
            # 错误 message
            print(error.message)
            # 诊断地址
            print(error.data.get("Recommend"))
            UtilClient.assert_as_string(error.message)


if __name__ == '__main__':
    Sample.main(sys.argv[1:])
