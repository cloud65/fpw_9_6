import os
from aiohttp import web
from asyncio import Queue, create_task


class Client: # Класс подпискиков
    def __init__(self, socket):
        self._socket = socket
        self._queue = Queue()
        self._keepalive = True
        self._task = create_task(self.run())
        
    async def run(self):
        while self._keepalive:
            news = await self._queue.get()
            await self.send(news) 
            
    async def send(self, data):   
        await self._socket.send_str(data)
        
    async def close(self):
        self._keepalive = False
        #self._task.cancel()
        await self._socket.close()
        
    def __eq__(self, value):
        return self._socket==value
    
    async def add_news(self, data):
        await self._queue.put(data)
        
        

class Clients: # Класс управления подписчиками
    def __init__(self):
        self._clients = []
        self._news = []
        
    async def append(self, client):        
        for item in self._news:
            await client.add_news(item)
        self._clients.append(client)
        
    async def add_news(self, item):        
        self._news.append(item)
        for client in self._clients:
            await client.add_news(item)
            
    def remove(self, data):
        self._clients.remove(data)
        
    async def shutdown(self):
        for client in self._clients:
            await client.close()            
    
        

async def wshandler(request: web.Request):
    resp = web.WebSocketResponse(autoping=True)
    available = resp.can_prepare(request)
    if not available:
        with open(WS_FILE, "rb") as fp:
            return web.Response(body=fp.read(), content_type="text/html")

    await resp.prepare(request)

    try:
        print("Someone joined.")
        await request.app.clients.append(Client(resp))

        async for msg in resp:
            if msg.type == web.WSMsgType.TEXT:
                if msg.data=='#PING':
                    await resp.send_str('#PONG')
                    continue
            else:
                return resp
        return resp

    finally:
        request.app.clients.remove(resp)
        print("Someone disconnected.")


async def handlerAddNews(request: web.Request):
    code = request.charset or 'utf-8'
    b_text = await request.read()
    text = b_text.decode(code)
    print('Send news.')
    await request.app.clients.add_news(text)
    return web.Response(text="Ok")


async def on_shutdown(app: web.Application):
    await app.clients.shutdown()


def init():
    app = web.Application()
    app.clients = Clients()
    app.router.add_get("/", wshandler) 
    app.add_routes([web.post('/news', handlerAddNews)])
    app.on_shutdown.append(on_shutdown) 
    return app
    

if __name__=='__main__':
    WS_FILE = 'index.html'
    web.run_app(init(), port=9000)