# -*- coding: utf8 -*-
import re
import json
import random
import datetime
from session import Session


class _Report(object):
    """
    通用填报模板
    需要继承该类，重写 _form_id, _enc, _clean_form_data() 后使用
    """
    def __init__(self, username, password, school_id=''):
        """
        :params username: 手机号、邮箱或学号
        :params password: 密码
        :params school_id: 学校代码，使用学号登录才需填写
        """
        self._t = Time()

        self._username = username
        self._username_masked = '*' * (len(username) - 3) + username[-3:]
        self._password = password
        self._school_id = school_id

        self._session = Session(self._username).load_session()

        self._form_id = ''
        self._enc = ''
        self._reporter_name = '通用模板'
        self._result = ''
        self._last_form_data = {}
        self._today_form_data = {}
        self._check_code = ''
        self._submit_version= ''
        self._today_report_result = {}

    @staticmethod
    def _random_temperature() -> str:
        temperature = str(round(random.uniform(36.3, 36.7), 1))
        return temperature

    def _check_session(self) -> bool:
        """
        检测 session 是否仍有效
        """
        check_url = 'http://mooc1-1.chaoxing.com/api/workTestPendingNew'
        resp = self._session.get(check_url)
        if '登录' in resp.text:
            return False
        else:
            return True

    def _login(self) -> bool:
        """
        登录: 支持手机号、邮箱或学号登录
        """
        if self._check_session():
            return True

        login_api = "https://passport2.chaoxing.com/api/login"
        params = {
            "name": self._username,
            "pwd": self._password,
            "verify": "0",
            "schoolid": self._school_id
        }
        resp = self._session.get(login_api, params=params)

        if resp.status_code == 403:
            self._result = "%s登录得到403，登录请求被拒绝" % self._username_masked
            raise Exception(self._result)

        data = json.loads(resp.text)
        if not data['result']:
            self._result = '%s登录失败' % self._username_masked
            raise Exception(self._result)

        Session(self._username, self._session).save_session()
        return True

    def _get_last_form_data(self) -> dict:
        """
        获取上次提交的健康信息
        """
        params = {
            "cpage": "1",
            "formId": self._form_id,
            "enc": self._enc,
            "formAppId": ""
        }
        # api = 'http://office.chaoxing.com/data/apps/forms/fore/user/list'
        api = 'http://office.chaoxing.com/data/apps/forms/fore/forms/user/last/info'
        resp = self._session.get(api, params=params)
        raw_data = json.loads(resp.text)
        if not raw_data['data']:
            self._result = '%s获取上次%s提交数据为空！' % (self._username_masked, self._reporter_name)
            raise Exception(self._result)
        form_data = raw_data['data']['formsUser']['formData']
        d = {
            "inDetailGroupIndex": -1,
            "fromDetail": False,
            "isShow": True,
            "hasAuthority": True
        }
        for f in form_data:
            f.update(d)
        self._last_form_data = form_data
        # with open('last_form_data.json', 'w', encoding='utf8') as f:
        #     json.dump(self._last_form_data, f, ensure_ascii=False, indent=2)
        return self._last_form_data

    def _clean_form_data(self):
        """
        子类继承后重写该函数，用于提交数据的修改
        例如修改提交日期为当日，随机体温等
        """
        self._today_form_data = self._last_form_data

    def _get_check_code(self):
        """
        访问表单页面，并获取 check code
        """
        params = {
            'id': self._form_id,
            'enc': self._enc
        }
        form_url = "http://office.chaoxing.com/front/web/apps/forms/fore/apply"
        resp = self._session.get(form_url, params=params)
        code = re.findall(r"checkCode.*'(.*)'", resp.text)
        if code:
            self._check_code = code[0]
            return self._check_code
        else:
            self._result = "%s获取%s校验码失败" % (self._username_masked, self._reporter_name)
            raise Exception(self._result)

            
    def _get_submit_version(self):
        """
        访问表单页面，并获取 check code
        """
        params = {
            "formId": self._form_id,
            "formAppId": "",
            'enc': self._enc
        }
        form_url = "https://office.chaoxing.com/data/apps/forms/fore/user/info"
        resp = self._session.get(form_url, params=params)
        uptime = re.findall(r".updatetime.:(.*?),", resp.text)
        if uptime:
            self._submit_version = uptime[0]
            return self._submit_version
        else:
            self._result = "%s获取%ssubmitversion失败" % (self._username_masked, self._reporter_name)
            raise Exception(self._result)
            
    def _today_report(self) -> dict:
        """
        上报今日信息
        """
        save_api = "http://office.chaoxing.com/data/apps/forms/fore/user/save?lookuid=127973604"
        form_data = json.dumps(self._today_form_data)
        data = {
            "gatherId": "0",
            "formId": self._form_id,
            "formAppId": "",
            "version": "5",
            "checkCode": self._check_code,
            "enc": self._enc,
            "formData": form_data,
            "submitVersion": self._submit_version,
        }
        resp = self._session.post(save_api, data=data)
        self._today_report_result = json.loads(resp.text)
        return self._today_report_result

    def report(self) -> str:
        self._login()
        self._get_last_form_data()
        self._clean_form_data()
        self._get_check_code()
        self._get_submit_version()
        report_result = self._today_report()
        if report_result['success']:
            self._result = '%s填报%s(id=%s)成功' % (self._username_masked, self._reporter_name, self._form_id)
        else:
            self._result = '%s填报%s(id=%s)失败' % (self._username_masked, self._reporter_name, self._form_id)
            self._result += '，返回报错：%s' % report_result['msg']
        return self._result


class Time(object):
    """
    时间相关函数
    用于填报的时间判断
    """
    def __init__(self):
        self.datetime: datetime.datetime = self._get_now_time()
        self.today: str = self.datetime.strftime('%Y-%m-%d')
        self.report_time: str = self.datetime.strftime("%Y-%m-%d %H:%M")
        self.report_time_sec: str = self.datetime.strftime("%Y-%m-%d %H:%M:%S")
        self.hour: str = self.datetime.strftime("%H")
        self.minute: str = self.datetime.strftime("%M")

        self.int_hour: int = self.datetime.hour
        self.int_minute: int = self.datetime.minute

    def _get_now_time(self):
        t = datetime.datetime.utcnow()
        # 确保获取的是东八区时区时间
        t += datetime.timedelta(hours=8)
        self.datetime = t
        return self.datetime
