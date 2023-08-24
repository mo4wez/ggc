import os
import json
from pathlib import Path
from dotenv import load_dotenv
from exceptions import InvalidJsonConfigFileException


class GolestanGradeCheckerConfig:
    def __init__(self):
        try:
            self.term, self.login_url = self._read_config()
            self.token, self.api_id, self.api_hash = self._read_env_config()
        except InvalidJsonConfigFileException:
            exit(2)

    def _read_env_config(self):
        load_dotenv(verbose=False)
        env_path = Path('./env') / '.env'
        load_dotenv(dotenv_path=str(env_path))

        token = os.getenv("TOKEN")
        api_id = os.getenv("API_ID")
        api_hash = os.getenv("API_HASH")
        return token, api_hash, api_id

    def _read_config(self):
        with open('config.json') as f:
            data = json.load(f)

        if 'term_no' not in data:
            raise InvalidJsonConfigFileException('term_no')
        if 'tele_notif' not in data:
            raise InvalidJsonConfigFileException('golestan_login_url')


        return data['term_no'], data['golestan_login_url']
