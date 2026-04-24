from pydantic import BaseModel


class ShopItemOut(BaseModel):
    id: int
    name: str
    description: str | None = None
    price: int
    category: str


class ShopBuyRequest(BaseModel):
    item_id: int


class ShopPayRequest(BaseModel):
    amount: int


class ShopBuyResponse(BaseModel):
    message: str
    credits: int
    item: ShopItemOut


class SupplierKitItem(BaseModel):
    ingredient_id: int
    quantity: int


class SupplierKitResponse(BaseModel):
    message: str
    debt: int
    debt_level: int
    debt_level_name: str
    items: list[SupplierKitItem]


class ShopPayResponse(BaseModel):
    message: str
    credits: int
    debt: int
    debt_level: int
    debt_level_name: str
