function setCookie(name, value, days) {
    setCookieHours(name, value,days*24)
}
function setCookieHours(name, value, hours){
    var expires = "";
    if (hours) {
        var date = new Date();
        date.setTime(date.getTime() + (hours * 60 * 60 * 1000));
        expires = "; expires=" + date.toUTCString();
    }
    document.cookie = name + "=" + value + expires + "; path=/";
}
function getCookie(name) {
    var nameEQ = name + "=";
    var cookies = document.cookie.split(';');
    for (var i = 0; i < cookies.length; i++) {
        var cookie = cookies[i];
        while (cookie.charAt(0) == ' ') {
            cookie = cookie.substring(1, cookie.length);
        }
        if (cookie.indexOf(nameEQ) === 0) {
            return cookie.substring(nameEQ.length, cookie.length);
        }
    }
    return null;
}

function isSearchEngineBot() {
    var ua = navigator.userAgent.toLowerCase();
    return /googlebot|bingbot|baiduspider|yandexbot|duckduckbot|slurp|sogou|yisouspider|exabot|facebot|ia_archiver/.test(ua);
}
let loc = "";
function g_init(page,option){
    if (isSearchEngineBot()){
        return;
    }
    initAdvAndTipModal();
    loc = getCookie("ipLoc");
    if (loc){
        if (page && page == 'play'){
            setupPlayerClicks();
        }else {
            setupGlobalListClicks();
        }
    }else {
        fetch('https://www.cloudflare.com/cdn-cgi/trace')
            .then(res => {
                if (!res.ok) {
                    throw new Error('Network response was not ok');
                }
                return res.text();
            }).then(data => {
            let result = {};
            data.split(/[\r\n]+/).forEach(line => {
                let parts = line.split('=');
                if (parts[0]) {
                    let k = parts[0].trim();
                    let v = parts[1] ? parts[1].trim() : "";
                    result[k] = v;
                }
            });
            if (result && result.loc){
                loc = result.loc.toUpperCase();
                setCookie("ipLoc",loc,10);
                if (page && page == 'play'){
                    setupPlayerClicks();
                }else {
                    setupGlobalListClicks();
                }

            }
        }).catch(e => {
        });
    }
}
function isMobile() {
    return /Android|iPhone|iPad|iPod|Mobile|Windows Phone|BlackBerry|Opera Mini/i.test(
        navigator.userAgent
    );
}
function isHttpUrl(str) {
    return /^https?:\/\/[^\s/$.?#].[^\s]*$/i.test(str);
}
function getImgProxyDomain(){
    let arr = ["imgp1.ikanbot.eu.org", "imgp2.ikanbot.eu.org"];
    return arr[Math.floor(Math.random() * arr.length)];
}
function base64urlEncode(str) {
    return btoa(str)
        .replace(/\+/g, "-")
        .replace(/\//g, "_")
        .replace(/=+$/, "")
}
window.lazyLoadOptions = {
    threshold: 0,
    callback_enter: function (el) {
        const rawSrc = el.getAttribute("data-src");
        if (rawSrc && rawSrc.toLowerCase().includes("doubanio.com")) {
            const ecodeImgSrc = base64urlEncode(rawSrc);
            const imgId = el.id;
            if (imgId) {
                const newSrc = "https://imgp.ikanbot.eu.org/i/" + imgId + "?u=" + ecodeImgSrc;
                el.setAttribute("data-src", newSrc);
            }
        }
    },
    callback_error: (img) => {
        let imgSrc = img.src;
        if (!isHttpUrl(imgSrc)){
            return;
        }
        let imgId = img.id;
        if (imgId){
            if (imgSrc && imgSrc.toLowerCase().includes("ikanbot.eu.org")) {
                let proxyDomain = getImgProxyDomain();
                let newDomainSrc = imgSrc.replace("imgp.ikanbot.eu.org",proxyDomain);
                img.setAttribute("src",newDomainSrc);
            }else {
                img.setAttribute("src","/images/tv_default_medium.png");
            }
        }else {
            if (imgSrc && imgSrc.toLowerCase().includes("doubanio.com")) {
                let ecodeImgSrc = encodeURIComponent(imgSrc);
                var proxyDomain = getImgProxyDomain();
                img.setAttribute("src", "https://" + proxyDomain + "/proxy?url=" + ecodeImgSrc);
            }else {
                img.setAttribute("src","/images/tv_default_medium.png");
            }
        }


    }
};
window.addEventListener(
    "LazyLoad::Initialized",
    function (e) {
        //console.log(e.detail.instance);
    },
    false
);

function randomInt(min, max) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
}
const A_CONFIG = {
    routes:[
        { url: '/go/as', weight: 10 },
        { url: '/go/mtag', weight: 90 }
    ],
    cn_routes:[
        { url: '/go/cn1', weight: 90 },
        { url: '/go/cn2', weight: 10 }
    ],
    listClickThreshold: 3,
    adCoolDownMinutes: randomInt(20, 60)
};
const A_Store = {
    get: (k) => parseInt(localStorage.getItem(k)) || 0,
    set: (k, v) => localStorage.setItem(k, v),
    getLastIndex: (key = "last_index") => parseInt(localStorage.getItem(key) ?? "-1", 10),
    isCooldown: (k) => Date.now() < A_Store.get(k + '_expire'),
    setCooldown: (k, m) => localStorage.setItem(k + '_expire', Date.now() + m * 60000),
    isShowTip:()=> Date.now() > A_Store.get('adv_tip_expire'),
    setTipTimeout: (d) => localStorage.setItem('adv_tip_expire', Date.now() + d * 86400000)
};

function pickByWeight(routes) {
    const totalWeight = routes.reduce(
        (sum, route) => sum + route.weight,
        0
    );
    let rand = Math.random() * totalWeight;
    for (const route of routes) {
        rand -= route.weight;
        if (rand <= 0) {
            return route.url;
        }
    }
    return routes[0].url;
}
function pickIndexByWeight(routes, lastIndex = -1) {
    if (routes.length === 1) {
        return 0;
    }
    let totalWeight = 0;
    for (let i = 0; i < routes.length; i++) {
        if (i !== lastIndex) {
            totalWeight += routes[i].weight;
        }
    }
    let rand = Math.random() * totalWeight;
    for (let i = 0; i < routes.length; i++) {
        if (i === lastIndex) {
            continue;
        }
        rand -= routes[i].weight;
        if (rand <= 0) {
            return i;
        }
    }
    return 0;
}

function getTargetUrl() {
    // if (loc === "MY") {
    //     return A_CONFIG.routes[1].url;
    // }
    // if (loc === "US") {
    //     return A_CONFIG.routes[0].url;
    // }
    if (loc === "CN") {
        return getNextUrl(A_CONFIG.cn_routes);

    }
    return getNextUrl(A_CONFIG.routes);
}
function getNextUrl(routes) {
    let lastIndex = A_Store.getLastIndex();
    let index = pickIndexByWeight(routes, lastIndex);
    A_Store.set("last_index",index);
    return routes[index].url;
}
function setupGlobalListClicks() {
    document.body.addEventListener('click', function(e) {
        let target = e.target;
        let link = target.closest("a");
        if (!link) return;
        let href = link.getAttribute("href");
        if (!href || !href.includes("play")) return;
        if (e.isTrusted === undefined || e.isTrusted) {
            if (A_Store.isCooldown('ad_cooldown')) return;
            let clicks = A_Store.get('ad_list_clicks') + 1;
            if (clicks >= A_CONFIG.listClickThreshold) {
                let targetUrl = getTargetUrl();
                if (targetUrl && targetUrl !== ""){
                    window.open(targetUrl, '_blank');
                }
                A_Store.set('ad_list_clicks', 0);
                A_Store.setCooldown('ad_cooldown', A_CONFIG.adCoolDownMinutes);
            } else {
                A_Store.set('ad_list_clicks', clicks);
            }
        }
    });
}
function handlePlayerClick(e){
    if (!e.isTrusted) return;
    let trigger = e.target.closest(
        "#ikanbot-player, .vjs-big-play-button, .vjs-play-control, [name='lineData']"
    );
    if (!trigger) return;
    if (A_Store.isCooldown('ad_cooldown')) return;
    let targetUrl = getTargetUrl();
    if (targetUrl && targetUrl !== ""){
        window.open(targetUrl, '_blank');
    }
    A_Store.set('ad_list_clicks', 0);
    A_Store.setCooldown('ad_cooldown', A_CONFIG.adCoolDownMinutes);
}
function setupPlayerClicks(){
    document.addEventListener("click", handlePlayerClick,true);
    document.addEventListener("touchend", handlePlayerClick,true);
}
function initAdvAndTipModal(){
    let modal = '<!-- 自定义 Modal -->\n' +
        '<div id="advTipModal" class="modal" tabindex="-1" role="dialog" style="display: block">\n' +
        '    <div class="modal-dialog">\n' +
        '        <div class="modal-content">\n' +
        '\n' +
        '            <div class="modal-header">\n' +
        '                <h4 class="modal-title">安全提示</h4>\n' +
        '            </div>\n' +
        '\n' +
        '            <div class="modal-body">\n' +
        '                <p>跳转页面过程中遇到需要发送短信验证或者需要支付的情况，请不要相信，访问本站不会短信验证和收取任何费用，感谢您的理解。</p>\n' +
        '            </div>\n' +
        '\n' +
        '            <div class="modal-footer">\n' +
        '                <button type="button" class="btn btn-default" onclick="closeAdvModal()">知道了</button>\n' +
        '            </div>\n' +
        '\n' +
        '        </div>\n' +
        '    </div>\n' +
        '</div>';
    if (A_Store.isShowTip()) {
        $("body").append(modal);
    }
}
function closeAdvModal(){
    let advModal  = $("#advTipModal");
    if (advModal){
        advModal.hide();
    }
    A_Store.setTipTimeout(7);
}
