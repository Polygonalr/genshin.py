from __future__ import annotations

import asyncio
import heapq
from typing import *

from .models import ItemTransaction, Transaction, Wish
from .utils import amerge

if TYPE_CHECKING:
    from .client import GenshinClient


class IDModel(Protocol):
    id: int


T = TypeVar("T")
IDModelT = TypeVar("IDModelT", bound=IDModel, covariant=True)
TransactionT = TypeVar("TransactionT", bound=Transaction, covariant=True)


async def aenumerate(iterable: AsyncIterable[T], start: int = 0) -> AsyncIterator[Tuple[int, T]]:
    i = start
    async for x in iterable:
        yield i, x
        i += 1


async def aislice(iterable: AsyncIterable[T], stop: int = None) -> AsyncIterator[T]:
    """Slices an async iterable"""
    async for i, x in aenumerate(iterable, start=1):
        yield x

        if stop and i >= stop:
            return


class IDPagintor(Generic[IDModelT]):
    """A paginator of genshin prev_id pages

    Takes in a function with which to get the next few arguments
    """

    limit: Optional[int]
    end_id: Optional[int]

    page_size: int = 20

    def __init__(self, limit: int = None, end_id: int = 0) -> None:
        """Create a new paginator from alimit and the starting end id"""
        self.limit = limit
        self.end_id = end_id

    @property
    def exhausted(self) -> bool:
        return self.end_id is None

    def __repr__(self) -> str:
        return f"{type(self).__name__}(limit={self.limit})"

    async def function(self, end_id: int) -> List[IDModelT]:
        raise NotImplementedError

    async def next_page(self) -> List[IDModelT]:
        """Get the next page of the paginator"""
        if self.end_id is None:
            raise Exception("No more pages")

        data = await self.function(self.end_id)

        # mark paginator as exhausted
        if len(data) < self.page_size:
            self.end_id = None
            return data

        self.end_id = data[-1].id
        return data

    async def _iter(self) -> AsyncIterator[IDModelT]:
        """Iterate over pages until the end"""
        while not self.exhausted:
            page = await self.next_page()
            for i in page:
                yield i

    def __aiter__(self) -> AsyncIterator[IDModelT]:
        """Iterate over all pages unril the limit is reached"""
        return aislice(self._iter(), self.limit)

    async def flatten(self) -> List[IDModelT]:
        """Flatten the entire iterator into a list"""
        return [item async for item in self]


class AuthkeyPaginator(IDPagintor[IDModelT]):
    authkey: Optional[str]

    def __init__(self, authkey: str = None, limit: int = None, end_id: int = 0) -> None:
        super().__init__(limit=limit, end_id=end_id)
        self.authkey = authkey


class WishHistory(AuthkeyPaginator[Wish]):
    client: GenshinClient
    banner_type: int
    lang: Optional[str]

    def __init__(
        self, client: GenshinClient, banner_type: int, lang: str = None, **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)
        self.client = client
        self.banner_type = banner_type
        self.lang = lang

    async def _get_banner_name(self) -> str:
        """Get the banner name of banner_type"""
        banner_types = await self.client.get_banner_types(lang=self.lang, authkey=self.authkey)
        return banner_types[self.banner_type]

    async def function(self, end_id: int) -> List[Wish]:
        data = await self.client.request_gacha_info(
            "getGachaLog",
            lang=self.lang,
            authkey=self.authkey,
            params=dict(gacha_type=self.banner_type, size=self.page_size, end_id=end_id),
        )
        banner_name = await self._get_banner_name()
        return [Wish(**i, banner_name=banner_name) for i in data["list"]]


class MergedWishHistory(AuthkeyPaginator[Wish]):
    client: GenshinClient
    lang: Optional[str]
    banner_type: Literal[None] = None

    def __init__(self, client: GenshinClient, lang: str = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.client = client
        self.lang = lang

        self._paginators = [
            WishHistory(client, b, lang=self.lang, **kwargs) for b in (100, 200, 301, 302)
        ]
        self.__key: Callable[[Wish], int] = lambda wish: -wish.time.timestamp()

    def _iter(self) -> AsyncIterator[Wish]:
        return amerge(self._paginators, key=self.__key)

    async def flatten(self, *, lazy: bool = False) -> List[Wish]:
        # before we gather all histories we should get the banner name
        asyncio.create_task(self.client.get_banner_types(lang=self.lang, authkey=self.authkey))

        if self.limit is not None and lazy:
            it = aislice(amerge(self._paginators, key=self.__key), self.limit)
            return [x async for x in it]

        coros = (p.flatten() for p in self._paginators)
        lists = await asyncio.gather(*coros)
        return list(heapq.merge(*lists, key=self.__key))[: self.limit]


class Transactions(AuthkeyPaginator[TransactionT]):
    client: GenshinClient
    kind: str
    lang: Optional[str]

    def __init__(self, client: GenshinClient, kind: str, lang: str = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.client = client
        self.kind = kind
        self.lang = lang

    async def function(self, end_id: int):
        endpoint = "get" + self.kind.capitalize() + "Log"

        coro = self.client._get_transaction_reasons(self.lang or self.client.lang)
        reasons_task = asyncio.create_task(coro)

        data = await self.client.request_transaction(
            endpoint, lang=self.lang, authkey=self.authkey, params=dict(end_id=end_id, size=20)
        )

        reasons = await reasons_task

        transactions = []
        for trans in data["list"]:
            cls = ItemTransaction if "name" in trans else Transaction
            reason = reasons.get(trans["reason"], "")
            transactions.append(cls(**trans, reason_str=reason, kind=self.kind))

        return transactions


class MergedTransactions(AuthkeyPaginator[Union[Transaction, ItemTransaction]]):
    client: GenshinClient
    lang: Optional[str]
    kind: Literal[None] = None

    def __init__(self, client: GenshinClient, lang: str = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.client = client
        self.lang = lang

        self._paginators = [
            Transactions(client, kind, lang=self.lang, **kwargs)
            for kind in ("primogem", "crystal", "resin", "artifact", "weapon")
        ]
        self.__key: Callable[[Transaction], int] = lambda trans: -trans.time.timestamp()

    def _iter(self) -> AsyncIterator[Union[Transaction, ItemTransaction]]:
        return amerge(self._paginators, key=self.__key)

    async def flatten(self, *, lazy: bool = False) -> List[Union[Transaction, ItemTransaction]]:
        # before we gather all histories we should get the banner name
        asyncio.create_task(self.client.get_banner_types(lang=self.lang, authkey=self.authkey))

        if self.limit is not None and lazy:
            it = aislice(amerge(self._paginators, key=self.__key), self.limit)
            return [x async for x in it]

        coros = (p.flatten() for p in self._paginators)
        lists = await asyncio.gather(*coros)
        return list(heapq.merge(*lists, key=self.__key))[: self.limit]
