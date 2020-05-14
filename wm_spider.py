import copy
import random
import re
from pprint import pprint
from time import time, sleep
import psycopg2
import requests
import json
from redis import Redis
from proxy import abuyun

redis_filter_name = 'filter_poi'
class WM_Spider:
    def __init__(self,lat,lng,city_id='30'):
        self.conn = psycopg2.connect(database="mt_wm_test", user="postgres", password="mc930816", host="127.0.0.1", port="5432")
        self.cur = self.conn.cursor()
        self.redis = Redis(decode_responses=True)
        self.page = 2
        self.city = city_id
        self.lat = lat
        self.lng = lng
        self.proxy = None
        self.index_url = 'https://i.waimai.meituan.com/openh5'
        self.headers = {
            'Host': 'i.waimai.meituan.com',
            'Accept': 'application/json',
            'Origin': 'https://h5.waimai.meituan.com',
            'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0.1; Redmi Note 3 Build/MMB29M; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/68.0.3440.91 Mobile Safari/537.36 TitansX/11.19.6 KNB/1.2.0 android/6.0.1 mt/com.sankuai.meituan/10.0.202 App/10120/10.0.202 MeituanGroup/10.0.202',
            'Referer': 'https://h5.waimai.meituan.com/waimai/mindex/menu?dpShopId=&mtShopId=1112840116809435&utm_source=wandoujia&channel=mtjj&source=shoplist&initialLat=22.544568&initialLng=113.949059&actualLat=22.544568&actualLng=113.949059',
            'Accept-Encoding': 'gzip, deflate',
            'Accept-Language': 'zh-CN,en-US;q=0.9',
            'Cookie': 'cityid={city_id}; uuid=450940DF938B12BD8AAC598D8CF4678D69BDD48C75BE2CD34A3C20CA525B3490; utm_medium=android; utm_term=1000000202; utm_content=861735030994726; w_actual_lat={w_actual_lat}; w_actual_lng={w_actual_lng}'.format(city_id=city_id,w_actual_lat=self.lat,w_actual_lng=self.lng),
            'X-Requested-With': 'com.sankuai.meituan',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Connection': 'keep-alive',
        }

    # 'https://i.waimai.meituan.com/openh5/channel/kingkongshoplist?_=1589286163907'
    def request_list_from_category(self,firstCategoryId,secondCategoryId,page,last_url='/channel/kingkongshoplist'):
        kwargs = {
            'startIndex': str(int(page) - 1),
            'firstCategoryId':firstCategoryId,
            'secondCategoryId':secondCategoryId,
            'wm_actual_latitude':self.lat,
            'wm_actual_longitude':self.lng
        }
        payload = 'startIndex={startIndex}&navigateType=910&firstCategoryId={firstCategoryId}&secondCategoryId={secondCategoryId}&geoType=2&platform=3&partner=4&originUrl=https://h5.waimai.meituan.com/waimai/mindex/kingkong?navigateType=910&firstCategoryId={firstCategoryId}&secondCategoryId={secondCategoryId}&title=%E7%BE%8E%E9%A3%9F&riskLevel=71&optimusCode=10&wm_actual_latitude={wm_actual_latitude}&wm_actual_longitude={wm_actual_longitude}&openh5_uuid=450940DF938B12BD8AAC598D8CF4678D69BDD48C75BE2CD34A3C20CA525B3490'.format_map(kwargs)

        url = self.index_url + last_url + '?_=' + str(int(time() * 1000))

        response_json = self.post_request(url,self.headers,payload)
        return response_json

    # 'https://i.waimai.meituan.com/openh5/poi/food?_=1589277696918'
    def request_detail_food(self,poi_id,last_url='/poi/food'):
        payload = 'mtWmPoiId={mtWmPoiId}&openh5_uuid=450940DF938B12BD8AAC598D8CF4678D69BDD48C75BE2CD34A3C20CA525B3490'.format(mtWmPoiId=poi_id)
        url = self.index_url + last_url + '?_=' + str(int(time() * 1000))
        response_json = self.post_request(url,self.headers,payload)
        food_category_list = response_json['data']['categoryList']
        hot_foods = []
        for food_category in food_category_list:
            if '热销' in food_category['categoryName']:
                hot_foods.append(food_category)
        return json.dumps(hot_foods)
    # 'https://i.waimai.meituan.com/openh5/poi/info?_=1589277696918'
    def request_detail_info(self,poi_id,last_url='/poi/info'):
        payload = 'mtWmPoiId={mtWmPoiId}&openh5_uuid=450940DF938B12BD8AAC598D8CF4678D69BDD48C75BE2CD34A3C20CA525B3490'.format(mtWmPoiId=poi_id)
        url = self.index_url + last_url + '?_=' + str(int(time() * 1000))
        response_json = self.post_request(url,self.headers,payload)
        kwargs = {}
        # 商家服务
        kwargs['mark'] = response_json['data']['brandMsg'] if 'brandMsg' in response_json['data'].keys() else ''
        # 营业时间
        kwargs['business_time'] = response_json['data']['serTime']
        kwargs['address'] = response_json['data']['shopAddress']
        #经纬度
        kwargs['address_gps_long'] = response_json['data']['shopLng']
        kwargs['address_gps_lat'] = response_json['data']['shopLat']
        return kwargs



    # 'https://i.waimai.meituan.com/openh5/poi/comments?_=1589353892512'
    def request_detail_comments(self,poi_id,last_url='/poi/comments'):
        # 如果有问题把 " w_actual_lat=22544568; w_actual_lng=113949059" 拼接到cookie
        headers = copy.deepcopy(self.headers)
        headers['Cookie'] = 'cityid={city_id}; network=wifi; utm_medium=android; utm_term=1000000202; utm_content=861735030994726; _lxsdk_cuid=171f918eca2c8-0a4e8cc73bc7e7-7452c56-38400-171f918eca5c8; _lxsdk=450940DF938B12BD8AAC598D8CF4678D69BDD48C75BE2CD34A3C20CA525B3490; _lxsdk_s=1720cdf3bd3-4f6-026-814%7C-1%7CNaN;'.format(city_id=self.city)

        payload = 'mtWmPoiId={mtWmPoiId}&startIndex=0&platform=3&partner=4&originUrl=https%3A%2F%2Fh5.waimai.meituan.com%2Fwaimai%2Fmindex%2Fmenu%3FdpShopId%3D%26mtShopId%3D891876934366856%26utm_source%3Dwandoujia%26channel%3Dmtjj%26source%3Dshoplist%26initialLat%3D%26initialLng%3D%26actualLat%3D22.544568%26actualLng%3D113.949059&riskLevel=71&optimusCode=10&openh5_uuid=450940DF938B12BD8AAC598D8CF4678D69BDD48C75BE2CD34A3C20CA525B3490'

        url = self.index_url + last_url + '?_=' + str(int(time() * 1000))
        response_json = self.post_request(url,headers=headers,payload=payload.format(mtWmPoiId=poi_id))

    def post_request(self,url,headers,payload):
        headers['Cookie'] = 'cityid=30; network=wifi; uuid=450940DF938B12BD8AAC598D8CF4678D69BDD48C75BE2CD34A3C20CA525B3490; utm_source=wandoujia; utm_medium=android; utm_term=1000000202; utm_content=861735030994726; wm_order_channel=mtjj; au_trace_key_net=default; openh5_uuid=450940DF938B12BD8AAC598D8CF4678D69BDD48C75BE2CD34A3C20CA525B3490; terminal=i; w_utmz="utm_campaign=(direct)&utm_source=5000&utm_medium=(none)&utm_content=(none)&utm_term=(none)"; openh5_uuid=450940DF938B12BD8AAC598D8CF4678D69BDD48C75BE2CD34A3C20CA525B3490; service-off=0; utm_campaign=AgroupBgroupC0E0Ghomepage_category1_394__a1__c-1024; channelType={%22mtjj%22:%220%22}; w_actual_lat=22546510; w_actual_lng=113948770'
        # if self.proxy == None:
        #     response = requests.post(url=url,headers=headers,data=payload)
        # else:
        #     response = requests.post(url=url, headers=headers, data=payload, proxies=self.proxy)
        response = requests.post(url=url, headers=headers, data=payload)
        return json.loads(response.content.decode())

    def work(self,firstCategoryId='910',secondCategoryId='100839'):
        has_next_page = True
        while has_next_page:
            print('当前页数------:',self.page)
            data = self.request_list_from_category(page=self.page,firstCategoryId=firstCategoryId,secondCategoryId=secondCategoryId)
            category_tags_l2_name,category_tags_l3_name = self.get_category(firstCategoryId,secondCategoryId)
            # 是否有下一页
            has_next_page = data['data']['poiHasNextPage']
            # 店铺列表
            for shop in data['data']['shopList']:
                self.proxy = abuyun()
                # 去重过滤
                if self.filter_poiId(shop['mtWmPoiId']):
                    print('这家店铺已存在-------：',shop['shopName'])
                    continue
                print('抓取店铺--------:',shop['shopName'],'$$$$',shop['mtWmPoiId'])
                cur_kwargs = {}
                cur_kwargs['source_data'] = '美团'
                cur_kwargs['category_tags_l1_name'] = '外卖'
                cur_kwargs['category_tags_l2_name'] = category_tags_l2_name
                # 快餐便当
                cur_kwargs['category_tags_l3_name'] = category_tags_l3_name
                shop_kwargs = self.process_shop_data(shop)
                cur_kwargs.update(shop_kwargs)
                # 获取商品信息 返回字符串 热销
                hot_foods = self.request_detail_food(poi_id=cur_kwargs['shopid'])
                cur_kwargs['popular_dishes'] = hot_foods
                # # 获取商铺信息
                info_kwargs = self.request_detail_info(poi_id=cur_kwargs['shopid'])
                cur_kwargs.update(info_kwargs)
                # # 获取商铺评论
                # # self.request_detail_comments(poi_id=cur_kwargs['shopid'])
                self.process_save_data(**cur_kwargs)
                self.filter_add(shop['mtWmPoiId'])
                print('插入成功----:',shop['shopName'] + '$$$$'+ shop['mtWmPoiId'])
                sleep(random.uniform(1,2))
            self.page += 1


    def process_shop_data(self,shop):
        # 所需数据
        kwargs = {}
        kwargs['shopname'] = shop['shopName']
        kwargs['shopid'] = shop['mtWmPoiId']
        kwargs['cityname'] = '深圳'
        # 起送价
        kwargs['minimum_charge'] = shop['minPriceTip']
        # 月售
        kwargs['mon_sales'] = shop['monthSalesTip']  # 有疑虑
        # 人均消费
        kwargs['avg_speed'] = shop['averagePriceTip']
        # 优惠活动
        kwargs['special_offer'] = shop['discounts2']
        return kwargs

    def process_save_data(self,**kwargs):
        # 行政区
        if '南山区' in kwargs['address']:
            kwargs['region'] = '南山区'
        else:
            kwargs['region'] = self.get_region(kwargs['address'])
        # 经纬度
        kwargs['address_gps_lat'] = str(float('%.7f' % kwargs['address_gps_lat']) / 1000000)
        kwargs['address_gps_long'] = str(float('%.7f' % kwargs['address_gps_long']) / 1000000)

        # 人均
        try:
            kwargs['avg_speed'] = float('%.2f' % int(kwargs['avg_speed'].replace('人均 ¥','')))
        except:
            kwargs['avg_speed'] = 0
        # 营业时间
        kwargs['business_time'] = kwargs['business_time'][0]
        # 起送
        print(kwargs['minimum_charge'])
        kwargs['minimum_charge'] = float('%.2f' % int(kwargs['minimum_charge'].replace('起送 ¥','')))
        # 月售
        kwargs['mon_sales'] = int(kwargs['mon_sales'].replace('月售','').replace('+',''))
        kwargs['special_offer'] = json.dumps(kwargs['special_offer'])
        print(kwargs)
        # 插入数据
        self.insert_data(**kwargs)


    def insert_data(self,**kwargs):
        # self.conn.ping(reconnect=True)
        sql = """insert into mt_wm (source_data,shopname,shopid,category_tags_l1_name,category_tags_l2_name,category_tags_l3_name,
        cityname,region,address,address_gps_long,address_gps_lat,popular_dishes,minimum_charge,mon_sales,avg_speed,business_time,
        special_offer,mark) values ('%(source_data)s','%(shopname)s','%(shopid)s','%(category_tags_l1_name)s','%(category_tags_l2_name)s',
        '%(category_tags_l3_name)s','%(cityname)s','%(region)s','%(address)s','%(address_gps_long)s','%(address_gps_lat)s','%(popular_dishes)s',
        '%(minimum_charge)f','%(mon_sales)d','%(avg_speed)f','%(business_time)s','%(special_offer)s','%(mark)s')""" %kwargs

        try:
            self.cur.execute(sql)
        except Exception as e:
            # print(e)
            pass
        self.conn.commit()


    def get_category(self,firstcategoryId,secondcategoryId):
        with open('cate_id.json','r',encoding='utf-8') as f:
            data = json.loads(f.read())
        firstcategoryname = data[firstcategoryId]
        secondcategoryname = data[secondcategoryId]
        return firstcategoryname,secondcategoryname

    def get_region(self,address):
        url = 'https://map.baidu.com/su?wd={}&cid=340&type=0&t=1589457215631'.format(address)
        headers = {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Connection': 'keep-alive',
        'Host': 'map.baidu.com',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36'
        }
        resp = requests.get(url,headers).content.decode()
        ret = json.loads(resp)
        region = ret['s'][0].split('$')[1]
        return region

    def filter_poiId(self,poiId):
        pass
        # return self.redis.sismember(redis_filter_name,poiId)

    def filter_add(self,poiId):
        pass
        # self.redis.sadd(redis_filter_name,poiId)



if __name__ == '__main__':
    mt_wm = WM_Spider(lat='22544568',lng='113949059')
    mt_wm.work()
    # mt_wm.get_category('910','102011')
    # mt_wm.get_region('北京大学')