from __future__ import annotations

import asyncio
import time
import urllib.parse
from collections import OrderedDict

from .http import PublicJSON
from .policy import CapabilityError, bounded_int


class Weather:
    def __init__(self, transport=None, *, ttl: int = 900):
        self.http=transport or PublicJSON(); self.ttl=ttl
        self.cache=OrderedDict(); self.lock=asyncio.Lock()

    async def get(self, city: str, *, country: str = 'CN', days: int = 3,
                  location_id: int | None = None) -> dict:
        bounded_int(days,1,3,'预报天数')
        if not isinstance(city,str) or not 2<=len(city.strip())<=60 or not country.isalpha() or len(country)!=2:
            raise CapabilityError('请提供具体城市；不会根据 IP 猜测所在地。')
        key=(city.strip(),country.upper(),days,location_id)
        async with self.lock:
            cached=self.cache.get(key)
            if cached and time.time()-cached[0]<self.ttl:
                self.cache.move_to_end(key)
                return dict(cached[1],cached=True)
            if city.strip().casefold().replace(' ','') in {'香港','香港特别行政区','香港特別行政區','hongkong','hk'}:
                # Explicitly chosen by the owner, not inferred from IP/location.
                candidates=[{'id':1819729,'name':'香港','admin1':'香港特别行政区','country':'中国香港',
                             'latitude':22.3193,'longitude':114.1694}]
            else:
                params=urllib.parse.urlencode({'name':city.strip(),'count':5,'language':'zh','format':'json','countryCode':country.upper()})
                result=await self.http.get('https://geocoding-api.open-meteo.com/v1/search?'+params,{'geocoding-api.open-meteo.com'})
                candidates=result.get('results',[])
            if location_id is not None:
                candidates=[x for x in candidates if x.get('id')==location_id]
            if not candidates: raise CapabilityError('没有找到这个城市，请补充省份或使用更明确的城市名。')
            if len(candidates)>1:
                return {'needs_location_choice':True,'candidates':[{k:x.get(k) for k in ('id','name','admin1','country')} for x in candidates],
                        'instruction':'向用户确认城市，再带 location_id 调用，不能随意选同名地点。'}
            place=candidates[0]
            params=urllib.parse.urlencode({'latitude':place['latitude'],'longitude':place['longitude'],
                'current':'temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code',
                'daily':'weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max',
                'forecast_days':days,'timezone':'auto'})
            forecast=await self.http.get('https://api.open-meteo.com/v1/forecast?'+params,{'api.open-meteo.com'})
            output={'provider':'Open-Meteo','source_url':'https://open-meteo.com/','location':{k:place.get(k) for k in ('name','admin1','country')},
                    'fetched_at':time.time(),'timezone':forecast.get('timezone'),'current':forecast.get('current'),
                    'current_units':forecast.get('current_units'),'daily':forecast.get('daily'),'daily_units':forecast.get('daily_units'),
                    'instruction':'说明地点和数据时间；这是预报数据，不能冒充气象预警或现场观测。'}
            self.cache[key]=(time.time(),output)
            while len(self.cache)>16: self.cache.popitem(last=False)
            return output
