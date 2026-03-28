def apply_stealth(page):
    try:
        page.add_init_script("""
            () => {
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['pt-BR', 'pt', 'en-US', 'en']
                });
                
                window.navigator.chrome = {
                    runtime: {},
                    loadTimes: function() {},
                    csi: function() {},
                    app: {}
                };
                
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
                
                Object.defineProperty(navigator, 'hardwareConcurrency', {
                    get: () => 8
                });
                
                Object.defineProperty(navigator, 'deviceMemory', {
                    get: () => 8
                });
                
                Object.defineProperty(navigator, 'platform', {
                    get: () => 'Win32'
                });
                
                Object.defineProperty(navigator, 'vendor', {
                    get: () => 'Google Inc.'
                });
                
                Object.defineProperty(navigator, 'maxTouchPoints', {
                    get: () => 0
                });
                
                delete navigator.__proto__.webdriver;
                
                const getParameter = WebGLRenderingContext.prototype.getParameter;
                WebGLRenderingContext.prototype.getParameter = function(parameter) {
                    if (parameter === 37445) {
                        return 'Intel Inc.';
                    }
                    if (parameter === 37446) {
                        return 'Intel Iris OpenGL Engine';
                    }
                    return getParameter.call(this, parameter);
                };
                
                const elementDescriptor = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'offsetHeight');
                Object.defineProperty(HTMLDivElement.prototype, 'offsetHeight', {
                    ...elementDescriptor,
                    get: function() {
                        if (this.id === 'modernizr') {
                            return 1;
                        }
                        return elementDescriptor.get.apply(this);
                    },
                });
                
                const originalToString = Function.prototype.toString;
                Function.prototype.toString = function() {
                    if (this === navigator.permissions.query) {
                        return 'function query() { [native code] }';
                    }
                    return originalToString.call(this);
                };
                
                ['height', 'width'].forEach(property => {
                    const imageDescriptor = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype, property);
                    Object.defineProperty(HTMLImageElement.prototype, property, {
                        ...imageDescriptor,
                        get: function() {
                            if (this.complete && this.naturalHeight == 0) {
                                return 20;
                            }
                            return imageDescriptor.get.apply(this);
                        },
                    });
                });
                
                Object.defineProperty(navigator.connection || {}, 'rtt', {
                    get: () => 100
                });
                
                if (!window.chrome) {
                    window.chrome = {};
                }
                if (!window.chrome.runtime) {
                    window.chrome.runtime = {};
                }
                
                const originalAddEventListener = EventTarget.prototype.addEventListener;
                EventTarget.prototype.addEventListener = function(type, listener, options) {
                    if (type === 'devtoolschange') {
                        return;
                    }
                    return originalAddEventListener.call(this, type, listener, options);
                };
                
                Object.defineProperty(navigator, 'doNotTrack', {
                    get: () => null
                });
                
                const mockPluginArray = {
                    length: 3,
                    0: {
                        name: 'Chrome PDF Plugin',
                        filename: 'internal-pdf-viewer',
                        description: 'Portable Document Format'
                    },
                    1: {
                        name: 'Chrome PDF Viewer',
                        filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai',
                        description: ''
                    },
                    2: {
                        name: 'Native Client',
                        filename: 'internal-nacl-plugin',
                        description: ''
                    }
                };
                
                Object.defineProperty(navigator, 'plugins', {
                    get: () => mockPluginArray
                });
            }
        """)
        
        page.evaluate("""
            () => {
                if (typeof document.hidden !== 'undefined') {
                    Object.defineProperty(document, 'hidden', {
                        get: () => false
                    });
                }
                if (typeof document.visibilityState !== 'undefined') {
                    Object.defineProperty(document, 'visibilityState', {
                        get: () => 'visible'
                    });
                }
            }
        """)
    except Exception as e:
        print(f"Erro ao aplicar stealth scripts: {e}")
