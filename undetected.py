import asyncio
import json
import os
import random
import shutil
import time
import zipfile
from datetime import datetime, timezone, timedelta

import nodriver
from nodriver import cdp
from nodriver.core.config import Config
from nodriver.core.util import start, logger


class UndetectedSetup:
    def __init__(self, profile_name="default", proxy=None):
        self.profile_path, self.user_agent = self.create_or_get_profile(profile_name)
        self.proxy = proxy
        self.config = self.setup_config()
        self.browser = None
        self.main_tab = None

    def create_proxy_extension(self):
        manifest_json = """
        {
            "version": "1.0.0",
            "manifest_version": 2,
            "name": "Chrome Proxy",
            "permissions": [
                "proxy",
                "tabs",
                "unlimitedStorage",
                "storage",
                "<all_urls>",
                "webRequest",
                "webRequestBlocking"
            ],
            "background": {
                "scripts": ["background.js"]
            },
            "minimum_chrome_version": "22.0.0"
        }
        """

        background_js = """
        var config = {
                mode: "fixed_servers",
                rules: {
                singleProxy: {
                    scheme: "http",
                    host: "%s",
                    port: parseInt(%s)
                },
                bypassList: ["localhost"]
                }
            };
        chrome.proxy.settings.set({value: config, scope: "regular"}, function() {});
        function callbackFn(details) {
            return {
                authCredentials: {
                    username: "%s",
                    password: "%s"
                }
            };
        }
        chrome.webRequest.onAuthRequired.addListener(
                    callbackFn,
                    {urls: ["<all_urls>"]},
                    ['blocking']
        );
        """ % (self.proxy['host'], self.proxy['port'], self.proxy['user'], self.proxy['pass'])

        extension_path = os.path.join(self.profile_path, 'proxy_extension')
        os.makedirs(extension_path, exist_ok=True)

        with open(os.path.join(extension_path, 'manifest.json'), 'w') as f:
            f.write(manifest_json)
        with open(os.path.join(extension_path, 'background.js'), 'w') as f:
            f.write(background_js)

        return extension_path

    def get_random_user_agent(self):
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0"
        ]
        return random.choice(user_agents)

    async def clear_browser_data(self):
        if self.main_tab:
            try:
                storage_types = ['cookies', 'local_storage', 'session_storage', 'indexeddb', 'websql', 'cache']
                for storage_type in storage_types:
                    await self.main_tab.send(cdp.storage.clear_data_for_origin(
                        origin='*',
                        storage_types=storage_type
                    ))
                # Очистка кэша
                await self.main_tab.send(cdp.network.clear_browser_cache())
                # Очистка куков
                await self.main_tab.send(cdp.network.clear_browser_cookies())
                logger.info("Browser data cleared successfully")
            except Exception as e:
                logger.error(f"Error clearing browser data: {e}")
        else:
            logger.warning("Main tab is not initialized, cannot clear browser data")

    def create_or_get_profile(self, profile_name):
        profiles_dir = os.path.join(os.getcwd(), "chrome_profiles")
        profile_path = os.path.join(profiles_dir, profile_name)

        if not os.path.exists(profile_path):
            os.makedirs(profile_path)

        metadata_path = os.path.join(profile_path, "metadata.json")
        if not os.path.exists(metadata_path):
            metadata = {
                "created_at": time.time(),
                "last_used": time.time(),
                "user_agent": self.get_random_user_agent()
            }
            with open(metadata_path, "w") as f:
                json.dump(metadata, f)
        else:
            with open(metadata_path, "r+") as f:
                metadata = json.load(f)
                metadata["last_used"] = time.time()
                f.seek(0)
                json.dump(metadata, f)
                f.truncate()

        return profile_path, metadata["user_agent"]


    def setup_config(self):
        config = Config(
            user_data_dir=self.profile_path,
            headless=False,
            lang='en-US,en,de-DE,de'  # Set accepted languages here
        )

        config.add_argument('--disable-gpu')
        config.add_argument('--disable-cookies')
        config.add_argument('--clear-token-service')
        config.add_argument('--purge-local-storage-on-exit')

        # Clear cookies and cache
        config.add_argument('--disable-cache')
        config.add_argument('--disable-application-cache')
        config.add_argument('--disable-offline-load-stale-cache')
        config.add_argument('--disk-cache-size=0')
        config.add_argument('--clear-cookies')
        config.add_argument('--clear-cache')

        # Set time zone for Germany
        config.add_argument('--timezone="Europe/Berlin"')

        # Disable translation
        config.add_argument('--disable-translate')

        if self.proxy:
            extension_path = self.create_proxy_extension()
            config.add_extension(extension_path)

        return config

    async def initialize_driver(self):
        try:
            self.browser = await nodriver.start(config=self.config)
            self.main_tab = self.browser.main_tab

            # Clear cookies
            await self.browser.cookies.clear()

            await self.clear_browser_data()
            await self.main_tab.set_window_size(width=1366, height=768)
            await self.mask_webdriver()
            await self.randomize_webgl()
            await self.set_german_time()
        except Exception as e:
            print(f"Error initializing driver: {e}")
            if self.browser:
                self.browser.stop()
            raise

    async def handle_request_paused(self, event: cdp.fetch.RequestPaused):
        await self.main_tab.send(cdp.fetch.continue_request(request_id=event.request_id))

    async def handle_auth_required(self, event: cdp.fetch.AuthRequired):
        await self.main_tab.send(cdp.fetch.continue_with_auth(
            request_id=event.request_id,
            auth_challenge_response=cdp.fetch.AuthChallengeResponse(
                response="ProvideCredentials",
                username=self.proxy['user'],
                password=self.proxy['pass']
            )
        ))

    async def navigate_to(self, url):
        try:
            await self.browser.get(url)
        except Exception as e:
            print(f"Error navigating to {url}: {e}")

    async def mask_webdriver(self):
        await self.main_tab.evaluate("""
        () => {
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Overwrite the `navigator.languages` property
            Object.defineProperty(navigator, 'languages', {
                get: () => ['de-DE', 'de']
            });
            
            // Overwrite the `navigator.plugins` property
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            // Overwrite the `navigator.permissions` property
            Object.defineProperty(navigator, 'permissions', {
                get: () => ({
                    query: async () => ({
                        state: 'granted',
                        status: 'granted'
                    })
                })
            });
        }
        """)

    async def randomize_webgl(self):
        await self.main_tab.evaluate("""
        const getParameter = WebGLRenderingContext.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {
          if (parameter === 37445) {
            return 'Intel Open Source Technology Center';
          }
          if (parameter === 37446) {
            return 'Mesa DRI Intel(R) Ivybridge Mobile ';
          }
          return getParameter(parameter);
        };
        """)

    async def set_german_time(self):
        german_time = datetime.now(timezone.utc) + timedelta(hours=1)
        await self.main_tab.evaluate(f"""
        Date.prototype.getTimezoneOffset = function() {{ return -60; }};
        Date.now = function() {{ return new Date({german_time.timestamp() * 1000}).getTime(); }};
        """)

    async def run_human_behavior(self, duration=30):
        end_time = time.time() + duration
        while time.time() < end_time:
            try:
                action = random.choice(['scroll', 'click', 'type'])
                if action == 'scroll':
                    await self.random_scroll()
                elif action == 'click':
                    await self.random_click()
                elif action == 'type':
                    await self.random_type()
                await asyncio.sleep(random.uniform(0.5, 2.0))
            except Exception as e:
                print(f"Error during human behavior simulation: {e}")

    async def random_scroll(self):
        await self.main_tab.evaluate(f"window.scrollTo(0, {random.randint(100, 1000)});")

    async def random_click(self):
        elements = await self.main_tab.query_selector_all('a, button, input[type="submit"]')
        if elements:
            element = random.choice(elements)
            await element.click()

    async def random_type(self):
        input_elements = await self.main_tab.query_selector_all('input[type="text"], textarea')
        if input_elements:
            input_element = random.choice(input_elements)
            await input_element.type(''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=random.randint(3, 10))))

    def get_page(self):
        return self.main_tab

    async def close_browser(self):
        if self.browser:
            self.browser.stop()

    async def __aenter__(self):
        await self.initialize_driver()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close_browser()


# Пример использования:
async def main():
    proxy = {
        'host': '45.13.195.53',
        'port': '30001',
        'user': 'vintarik8_gmail_com',
        'pass': 'c560667e15'
    }
    try:
        async with UndetectedSetup("my_profile", proxy=proxy) as setup:
            await setup.navigate_to("https://miles.plumenetwork.xyz/")
            await setup.run_human_behavior(duration=30)
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    asyncio.run(main())
