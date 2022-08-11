import enum
class Network(enum.Enum):
    BITCOIN = 'bitcoin'
    TESTNET = 'testnet'
    SIGNET  = 'signet'
    REGTEST = 'regtest'
    
from pydantic import BaseModel, validator
from datetime import datetime

class Candle(BaseModel):
    timestamp   : datetime
    open        : float
    high        : float
    low         : float
    close       : float
    volume      : float

    @validator('timestamp')
    def time_in_seconds(cls, v):
        result = v

        if type(v) is int and is_ms(v): 
            result = int(v * 1e-3)

        return result

    class Config:
        json_encoders = {
                datetime: lambda v: v.isoformat()
                }

