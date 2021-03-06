import os
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError, InvalidRequestError, SQLAlchemyError
from sqlalchemy import asc, desc
from db.ads.ads import AdAccount, AdMedia, AdFee, Products, Promotion, DailyBudget, MonthlyBudget, session,Device
import json
from datetime import datetime, timedelta, time
import pytz
import re
from utils.funcs import (remove_specified_key,
                         replace_key_name,
                         add_fields,
                         pickup_specified_key,
                         cast_to_dict,
                         str_to_int)

from db.ads.ads import CampaignReport, find_account_id, find_product_id, find_media_id


class AdAPItManager:
    def __init__(self, **kwargs):
        self._media_account_id = kwargs['media_account_id']

        self._type = kwargs['type']
        self.locale = 'ja'
        self.tz = 'Asia/Tokyo'
        self._params = {}
        self._granularity = 1
        self._range = 2
        self._today = datetime.combine(datetime.now(pytz.timezone(self.tz)), time())  # get today
        self._start_time = self._today - timedelta(days=self._range)
        self._end_time = self._today - timedelta(days=1)
        self._rows = []

    def initialize(self, session):
        pass

    # set locale
    def set_locale(self, locale, tz):
        self.locale = locale
        self.tz = tz

    @property
    def dataset(self):
        return self._rows

    @property
    def granularity(self):
        return self._granularity

    @granularity.setter
    def granularity(self, days):
        self._granularity = days

    @property
    def range(self):
        return self._range

    @range.setter
    def range(self, days):
        self._start_time = self._end_time - timedelta(days=days)
        self._range = days

    @property
    def start_time(self):
        return self._start_time

    @start_time.setter
    def start_time(self, start_time):
        print('>>>>>>>>>>')
        print(start_time)
        r = re.compile(r'\d{4}-\d{2}-\d{2}')  # ja
        # if isinstance(start_time, datetime):
        #     self._start_time = datetime.combine(start_time, time()).strftime('%Y-%m-%d')

        if isinstance(start_time, str) and r.match(start_time):
            self._start_time = start_time

        else:
            raise ValueError()

    @property
    def end_time(self):
        return self._end_time

    @end_time.setter
    def end_time(self, end_time):
        r = re.compile(r'\d{4}-\d{2}-\d{2}')  # ja
        # if isinstance(end_time, datetime):
        #     self._end_time = datetime.combine(end_time, time()).strftime('%Y-%m-%d')

        if isinstance(end_time, str) and r.match(end_time):
            self._end_time = end_time

        else:
            raise ValueError()

    # read key file
    def read_files(self, filename):
        this_dir = os.path.dirname(__file__)
        _filename = os.path.join(this_dir, filename)
        path = os.path.join(this_dir, filename)
        with open(_filename) as k:
            keys = json.load(k)
        return keys

    def date_to_int(self, dt_time):
        return 10000 * dt_time.year + 100 * dt_time.month + dt_time.day

    def validate_date_range(self):

        if isinstance(self._start_time, datetime) is False:
            self._start_time = datetime.strptime(self._start_time, '%Y-%m-%d')

        if isinstance(self._end_time, datetime) is False:
            self._end_time = datetime.strptime(self._end_time, '%Y-%m-%d')

        if self.date_to_int(self._start_time) - self.date_to_int(self._end_time) > 0:
            self._start_time = self._end_time - timedelta(days=1)

    ############################
    # Database
    ############################

    def insert_campaign_report(self):

        for row in self._rows:
            try:
                session.add(CampaignReport(**row))
                session.commit()

            except SQLAlchemyError as e:
                print(e)
                session.rollback()
                pass

    def upsert_campaign_report(self):
        for i, row in enumerate(self._rows):

            res = session.query(CampaignReport).filter(
                CampaignReport.date == row['date'],
                CampaignReport.promotion_id == row['promotion_id'],
                CampaignReport.campaign_id == row['campaign_id'],
                CampaignReport.adset_id == row['adset_id'])

            # UPDATE existing date
            try:
                # with session.begin(subtransactions=True):
                res.update(row)
                session.commit()


            except SQLAlchemyError as e:
                session.rollback()

            # INSERT new data
            if not res.first():
                try:
                    # with session.begin(subtransactions=True):
                    session.add(CampaignReport(**row))
                    session.commit()

                except IntegrityError as e:
                    print(e)
                    session.rollback()


                except SQLAlchemyError as e:
                    print(e)
                    session.rollback()
                    pass


class Manager:
    @classmethod
    def queue_all_tasks(cls):
        session = ads.session
        all_tasks = session.query(AdReportManager).filter(AdReportManager.reporting == True).all()

        fb = []
        tw = []
        adw = []
        im = []
        nend = []
        yh = []

        tw_id = ''
        im_id = ''
        nend_id = ''

        for all_task in all_tasks:

            items = {
                'media_account_id': all_task.media_account_id,
                'type': all_task.type,
                'type_account': []
            }

            # i-mobile
            if all_task.Promotion.AdMedia.id == 1:
                try:
                    if im_id != all_task.media_account_id:
                        items['type_account'].append(
                            {'media_campaign_id': all_task.media_campaign_id, 'promotion_id': all_task.Promotion.id})
                        im.append(items)

                    # last obj has same tw_id  so pick up last one as [-1]
                    else:
                        im[-1]['type_account'].append(
                            {'media_campaign_id': all_task.media_campaign_id, 'promotion_id': all_task.Promotion.id})

                    # set for avoiding duplication
                    im_id = all_task.media_account_id

                except IndexError as e:
                    print(e)
                    pass

            # twitter
            elif all_task.Promotion.AdMedia.id == 2:
                try:

                    if tw_id != all_task.media_account_id:
                        items['type_account'].append(
                            {'device': all_task.Promotion.device, 'promotion_id': all_task.Promotion.id})
                        tw.append(items)

                    # last obj has same tw_id  so pick up last one as [-1]
                    else:
                        tw[-1]['type_account'].append(
                            {'device': all_task.Promotion.device, 'promotion_id': all_task.Promotion.id})
                    tw_id = all_task.media_account_id

                except IndexError as e:
                    print(e)
                    pass

            # facebook
            elif all_task.Promotion.AdMedia.id == 3:
                items.update({'promotion_id': all_task.Promotion.id, })
                fb.append(items)

            # nend
            elif all_task.Promotion.AdMedia.id == 4:
                try:
                    if nend_id != all_task.media_account_id:
                        items['type_account'].append(
                            {'device': all_task.Promotion.device, 'media_campaign_id': all_task.media_campaign_id,
                             'promotion_id': all_task.Promotion.id})
                        nend.append(items)

                    # last obj has same tw_id  so pick up last one as [-1]
                    else:
                        nend[-1]['type_account'].append(
                            {'device': all_task.Promotion.device, 'media_campaign_id': all_task.media_campaign_id,
                             'promotion_id': all_task.Promotion.id})

                    # set for avoiding duplication
                    nend_id = all_task.media_account_id

                except IndexError as e:
                    print(e)
                    pass

            # add campaign field if type is "campaign"
            if all_task.type == 'campaign':
                items.update({'media_campaign_id': all_task.media_campaign_id})

        return im, tw, fb, nend

    @classmethod
    def select_campaign_report_all(cls):
        session = ads.session
        accounts = session.query(AdAccount).join(Promotion).all()
        services = session.query(Products).join(Promotion).all()
        medias = session.query(AdMedia).join(Promotion).all()

        datasets = session.query(Promotion).join(AdAccount, Products, AdMedia).all()

        for dataset in datasets:
            print('>>>>>>>>>>>>')
            print(
                dataset.id,
                dataset.promotion,
                dataset.AdAccount.account_name,
                dataset.Products.product_name,
                dataset.AdMedia.media_name,

            )

            # for result in results:
            #     for res in result:
            #         print(res)

    def join_ad_fee(self):
        pass


class Register:
    ##########################################
    # Resister
    ##########################################

    def __init__(self):
        self._account_id = ''

    def resister_ad_account(self, name):

        _name = {'account_name': name}

        try:
            session.add(AdAccount(**_name))
            session.commit()
            account_name = session.query(AdAccount).filter(AdAccount.account_name == _name['account_name']).one()
            self._account_id = account_name.id
            return self._account_id

        except SQLAlchemyError as e:
            print(e)
            session.rollback()
            pass

    def resister_ad_media(self, name):

        _name = {'media_name': name}

        try:
            session.add(AdMedia(**_name))
            session.commit()
        except SQLAlchemyError as e:
            print(e)
            session.rollback()
            pass

    def resister_products(self, id, name):

        _name = {
            'account_id': id,
            'product_name': name
        }

        try:
            session.add(Products(**_name))
            session.commit()
            product = session.query(Products).filter(Products.product_name == _name['product_name']).one()
            return product.id


        except SQLAlchemyError as e:
            print(e)
            session.rollback()
            pass

    def resister_ad_fee(self, **kwargs):

        p_id = kwargs.get('id', False)
        fee = kwargs.get('fee', 1.0)

        # empty is not allowed
        if p_id == '':
            print('something is empty')
            return False

        _fee = {
            'promotion_id': p_id,
            'fee': fee,
        }

        try:
            session.add(AdFee(**_fee))
            session.commit()

        except SQLAlchemyError as e:
            print(e)
            session.rollback()
            pass

    def resister_daily_budget(self, **kwargs):
        p_id = kwargs.get('id', False)
        annually = kwargs.get('annually', False)
        monthly = kwargs.get('monthly', False)
        daily = kwargs.get('daily', False)
        at = kwargs.get('at', False)
        start = kwargs.get('start', False)
        end = kwargs.get('end', False)

        _budget = {
            'promotion_id': p_id,
        }

        if not annually and not monthly and not daily:
            print('you have to set at least one col from "annually" "monthly" "daily" ')

        # empty is not allowed
        if '' in [p_id, annually, monthly, daily, at, start, end, ]:
            print('something is empty')
            return False

        try:
            # validate period
            # has to be set at least at or start-end
            if not at and not start:
                # print('you have to set "at" or "start-end"')

                if annually:
                    _budget.update({'annually': annually})

                elif monthly:
                    _budget.update({'monthly': monthly})

                elif daily:
                    _budget.update({'daily': daily})

                session.add(DailyBudget(**_budget))
                session.commit()

            else:
                # type must to be string
                if at:
                    print('here')
                    _budget.update({'at': datetime.strptime(at, '%Y-%m-%d')})

                # type must to be string
                elif not end:
                    _budget.update({'start': datetime.strptime(start, '%Y-%m-%d'), 'end': end_of_month(1)})

                else:
                    _budget.update(
                        {'start': datetime.strptime(start, '%Y-%m-%d'), 'end': datetime.strptime(end, '%Y-%m-%d')})

                session.add(DailyBudget(**_budget))
                session.commit()

        except SQLAlchemyError as e:
            print(e)
            session.rollback()
            pass

    def resister_promotion(self, account_id,product_id,media_id,device):

        _promotion = {
            'account_id': account_id,
            'product_id': product_id,
            'media_id': media_id,
            'device': device,
        }

        try:
            session.add(Promotion(**_promotion))
            session.commit()


        except SQLAlchemyError as e:
            print(e)
            session.rollback()
            pass

    def resister_ad_report_manager(self, **kwargs):
        session = ads.session

        p_id = kwargs.get('promotion_id', False)
        media_account_id = kwargs.get('media_account_id', False)
        media_campaign_id = kwargs.get('media_campaign_id', False)

        _promotion_id = {
            'promotion_id': p_id,
            'media_account_id': media_account_id,
            'media_campaign_id': media_campaign_id,
        }

        try:
            session.add(AdReportManager(**_promotion_id))
            session.commit()

        except SQLAlchemyError as e:
            print(e)
            session.rollback()
            pass

    ##########################################
    # Update
    ##########################################

    def update_ad_account(self, id, name):

        try:
            target = session.query(AdAccount).filter(AdAccount.id == id).first()
            target.account_name = name
            session.commit()
        except SQLAlchemyError as e:
            session.rollback()

    def update_ad_media(self, id, name):

        try:
            target = session.query(AdMedia).filter(AdMedia.id == id).first()
            target.media_name = name
            session.commit()
        except SQLAlchemyError as e:
            session.rollback()

    def update_products(self, id, name):

        try:
            target = session.query(Products).filter(Products.id == id).first()
            target.product_name = name
            session.commit()
        except SQLAlchemyError as e:
            session.rollback()

    def update_ad_fee(self, id, **kwargs):
        session = ads.session

        try:
            target = session.query(AdFee).filter(AdFee.id == id).first()

            _target = kwargs.get('target', False)
            _fee = kwargs.get('fee', False)

            if target:
                target.tarfet = _target

            target.fee = _fee
            session.commit()
        except SQLAlchemyError as e:
            session.rollback()

    def update_ad_budget(self, id, **kwargs):

        _budget = kwargs.get('_budget')

        try:
            target = session.query(DailyBudget).filter(DailyBudget.id == id).first()

            if _budget:
                target.budget = _budget

            session.commit()
        except SQLAlchemyError as e:
            session.rollback()

    #
    # def update_media(self, id, name):
    #     try:
    #         target = session.query(Promotion).filter(Promotion.id == id).first()
    #         target.promotion_id = name
    #         session.commit()
    #     except SQLAlchemyError as e:
    #         session.rollback()
    #

    def update_ad_report_manager(self, id, reporting, media_campaign_id=None):

        res = session.query(AdReportManager.media_campaign_id).filter(AdReportManager.id == id).first()

        try:
            res.reporting = reporting

            if not res and media_campaign_id:
                res.media_campaign_id = media_campaign_id

            session.commit()
        except SQLAlchemyError as e:
            session.rollback()


class Manipulator:
    def __init__(self):
        self._result = []

    def get_media_name(self):
        session = ads.session
        medias = []

        results = session.query(
            Promotion
        ).join(AdMedia, Products).all()

        for result in results:
            medias.append((result.id, result.product_id, result.Products.id, result.Products.product_name,
                           result.AdMedia.media_name))

        return medias

    def sum_by_campaign(self):
        session = ads.session

        media_ids_names = self.get_media_name()
        joined = []
        campaigns = session.query(
            CampaignReport.promotion_id,
            CampaignReport.date,
            CampaignReport.device,
            label('spend', func.sum(CampaignReport.spend)),
            label('cvs', func.sum(CampaignReport.cvs)),
        ).join(Promotion, AdMedia).filter(CampaignReport.date == '2017-03-20').group_by(
            CampaignReport.date, CampaignReport.promotion_id, CampaignReport.device,
        ).order_by(asc(CampaignReport.promotion_id)).all()

        for i, campaign in enumerate(campaigns):
            try:
                for id_name in media_ids_names:
                    print('>>>>>>>>>>>>')
                    print(campaign)
                    print(id_name)
                    if campaign[0] == id_name[0]:
                        joined.append({
                            'id': media_ids_names[0],
                            'date': campaign[0],
                            'media': campaign[1],
                            'device': campaign[2],
                            'spend': campaign[3],
                            'cvs': campaign[4],
                            'cpi': campaign[3] / campaign[4],

                        })

            # if media.spend > 0:
            #     print(
            #         media.date,
            #         media.spend,
            #         # media.Promotion.AdMedia.media_name,
            #         media.product_name,
            #         media.device,
            #         media.spend / media.cvs,
            #
            #           # media[0].Promotion.AdMedia.media_name
            #           )
            except ZeroDivisionError:
                pass
        print(joined)
        # print( media[1].date,media[0].media_name , media[1].spend, media[1].campaign_name, media[1].cvs)
        # for camp in media.CampaignReport:
        #     if camp.spend > 0:
        #         print('>>>>>>>>>>>>>>>>')
        #         print(
        #             media.AdMedia.media_name,
        #             camp.date,
        #             camp.spend,
        #             camp.cvs,
        #             camp.campaign_name,
        #             camp.spend,
        #             camp.spend / camp.cvs,
        #     )
        print()
        #     for j,camp in enumerate(media):
        #         print(camp)
        #         if media[i].CampaignReport[j].spend > 0:
        #             print('>>>>>>>>>>>>>>>>')
        #             print(
        #                 media[i].AdMedia.media_name,
        #                 media[i].CampaignReport[j].date ,
        #                 media[i].CampaignReport[j].spend ,
        #                 media[i].CampaignReport[j].cvs ,
        #                 media[i].CampaignReport[j].campaign_name ,
        #                 media[i].CampaignReport[j].spend ,
        #                 media[i].CampaignReport[j].spend / media[i].CampaignReport[j].cvs ,
        #                   )
        #
        # t = CampaignReport
        #
        # result = session.query(
        #
        #     t.date,
        #     # t.promotion_id,
        #     t.campaign_name,
        #     label('spend', func.sum(t.spend)),
        #     label('cvs', func.sum(t.cvs)),
        #     label('impressions', func.sum(t.impressions)),
        #     label('clicks', func.sum(t.clicks)),
        # ).join(Promotion,AdMedia).filter(t.date == '2017-03-20').group_by(
        #     t.date,t.campaign_name,AdMedia.media_name,
        # ).order_by(asc(t.date)).all()
        #
        # self._result = result

    def sum_by_campaigns(self):
        session = ads.session
        t = CampaignReport

        result = session.query(
            AdMedia.media_name,
            t.date,
            t.promotion_id,
            t.campaign_name,
            func.sum(t.spend),
            'cvs', func.sum(t.cvs),
            label('impressions', func.sum(t.impressions)),
            label('clicks', func.sum(t.clicks)),
        ).join(Promotion).filter(t.date == '2017-03-20').group_by(
            AdMedia.media_name,
            t.date,
            t.promotion_id,
            t.campaign_name,
            t.spend,
            t.cvs,
            # t.impressions,
            # t.clicks,

        ).order_by(asc(t.date)).all()

        self._result = result

    def shape_group_by(self):
        session = ads.session
        rows = []
        for res in self._result:
            print('>>>>>>>>>>>>>')
            if res.spend > 0:
                row = {
                    'date': res.date,
                    'campaign_name': res.campaign_name,
                    'spend': res.spend,
                    'cvs': res.cvs,
                    'cpi': int(res.spend / res.cvs),
                    'cpc': int(res.spend / res.clicks),
                    'impressions': res.impressions,
                    'clicks': res.clicks,
                    # 'media':res[0].media_name,
                    'media2': res,
                }
                rows.append(row)
            else:
                row = {
                    'date': res.date,
                    'campaign_name': res.campaign_name,
                    'spend': res.spend,
                    'cvs': res.cvs,
                    'cpi': 0,
                    'impressions': res.impressions,
                    'clicks': res.clicks,
                    # 'media':res[0].media_name,
                    'media2': res,
                }
                rows.append(row)
        return rows


class Get:
    def get_accounts(self):
        store = []
        accounts = session.query(AdAccount).order_by(asc(AdAccount.id)).all()
        for account in accounts:
            act = {
                'id': account.id,
                'account_name': account.account_name
            }
            store.append(act)

        print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')
        print(store)

        return store

    def get_account(self, id):
        account = session.query(AdAccount).filter(AdAccount.id == id).one()
        act = {
            'id': account.id,
            'account_name': account.account_name
        }
        return act

    def get_meidas(self):
        store = []
        medias = session.query(AdMedia).all()
        for media in medias:
            p = {
                'id': media.id,
                'media_name': media.media_name,
            }
            store.append(p)
        return store

    def get_device(self):
        store = []
        devices = session.query(Device).all()
        for device in devices:
            p = {
                'id': device.id,
                'device': device.device,
            }
            store.append(p)
        return store

    def get_products(self, id):
        store = []
        products = session.query(Products).filter(Products.account_id == id).all()
        for product in products:
            p = {
                'id': product.id,
                'product_name': product.product_name,
                'account_is': product.AdAccount.id,
                'account_name': product.AdAccount.account_name,

            }
            store.append(p)
        return store

    def get_all_products(self):
        store = []
        products = session.query(Products).order_by(asc(Products.product_name)).all()
        for product in products:
            p = {
                'id': product.id,
                'product_name': product.product_name,
                'account_id': product.AdAccount.id,
                'account_name': product.AdAccount.account_name,

            }
            store.append(p)
        return store

    def get_product(self, id):
        product = session.query(Products).filter(Products.id == id).one()
        _product = {
            'id': product.id,
            'product_name': product.product_name,
            'account_is': product.AdAccount.id,
            'account_name': product.AdAccount.account_name,

        }
        print(_product)
        return _product

    def get_promotions(self):
        store=[]
        promotions = session.query(Promotion).order_by(asc(Promotion.id)).all()
        for promotion in promotions:
            pr = {
                'id': promotion.id,
                'media_name': promotion.AdMedia.media_name,
                'product_name': promotion.Products.product_name,
                'account_name': promotion.AdAccount.account_name,
                'device': promotion.device,
            }
            # for report in promotion.AdReportManager:
            #     pr.update({'reporting': report.reporting})
            store.append(pr)
                # print(report.reporting)
        print(store)
        return store
