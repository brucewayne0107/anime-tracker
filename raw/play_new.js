$(function () {
    //wechat warm
    // var isWexin = isWeixn();
    // if (isWexin){
    //     var weixinWarm = $("#wechat-warn");
    //     weixinWarm.html("由于网页脚本被污染，造成很多用户访问被恶意跳转，目前已更换，如再出现请清空浏览器缓存后再访问。");
    //     weixinWarm.show();
    // }
    //init player
    var showPlayer = "ikanbot-player";
    var player = videojs(showPlayer, {
        controls: true,
        controlBar: {
            skipButtons: {
                forward: 10,
                backward: 10
            }
        },
        preload: 'auto',
        autoplay: false,
        language: 'zh-CN',
        playbackRates: [0.5, 1, 1.5, 2]
    }, function () {
        //player already
    });
    try {
        player.titleBar.update({
            title: '警告：请切勿相信播放视频中的任何广告。',
            description:'强烈建议使用谷歌浏览器(Chrome)，视频资源加载更流畅，兼容性更好。'

        });
    }catch (e) {
        //版本不支持 titlebar
    }

    var isMobileScreen = true;
    function sizeChangeFunction(x) {
        let playerWrap = $("#player-wrap");
        if (x.matches) {
            isMobileScreen = true;
            $("#m-player").empty();
            $("#pc-player").empty();
            $("#m-player").append(playerWrap);

        } else {
            isMobileScreen = false;
            $("#m-player").empty();
            $("#pc-player").empty();
            $("#pc-player").append(playerWrap);
        }
    }
    var windowResize = window.matchMedia("(max-width: 991px)");
    sizeChangeFunction(windowResize);
    windowResize.addEventListener('change',sizeChangeFunction);

    var playerList = $("#video-list .item");
    if(playerList.length > 0){
        playerList.on("click", function () {
            var currentId = $("#current_id").val();
            var articleTitle = $("#article_title").val();
            var dataId = $(this).attr('data-id');
            var mtype = $(this).attr('mtype');
            if (currentId == dataId){
                return;
            }
            $("#video-list .item").removeClass("active");
            $(this).addClass("active");
            var title = $(this).find(".title").text();

            $("#current_id").val(dataId);
            $("#mtype").val(mtype);
            $("#video_title").text(title);
            var showTitle = title + (articleTitle ? ('-' + articleTitle + '片单播放列表') : '') + "-爱看机器人-ikanbot.com";
            $("title").text(showTitle);
            loadResData();
        });
    }
    loadResData();
    var curChoiceLine;
    let isFirstPlay = true;
    function loadResData(){
        var loadVideoId = $("#current_id").val();
        var mtype = $("#mtype").val();
        var loadingHtml = '<li class="clearfix loaderbox">' +
            '                        <div class="loader" style="float: left;"></div>' +
            '                        <span style="float: left;line-height: 25px;margin-left: 5px;">线路加载中......</span>' +
            '                    </li>';
        $('#lineContent').html(loadingHtml);
        var tk = "";
        try {
            tk = v_tks || "";
        }catch (e){
        }
        $.ajax({
            url:"/api/getResN",
            type:"get",
            data:{videoId:loadVideoId,mtype:mtype,token:tk},
            success:function (response){
                var respState = response.state;
                if (respState == 1){
                    var dataList = response.data.list;
                    if (dataList && dataList.length > 0){
                        var linesHtml = '';
                        let lineCount = dataList.length;
                        try {
                            $("#line-count-stat").html("（共"+lineCount+"条）");
                        }catch (e){
                            //do nothing
                        }
                        dataList.forEach(function (item, index) {
                            var lineId = item.id;
                            var lineName = "线路"+(index + 1);
                            var res = eval(item.resData);
                            var urlHtml = "";
                            if (res && res.length > 0) {
                                for (var j = 0 ;j < res.length;j++){
                                    var lineUrlData = res[j].url;
                                    var newName = res[j].newName;
                                    if (newName && newName != "" && isNaN(newName) && mtype && mtype != 1){
                                        urlHtml += '<span style="border: none;background: none;font-weight: bold;margin-right: 13px;margin-top: 10px;height: 40px;line-height: 40px;float: left;' +
                                            'padding: 0px 20px;">'+newName+'</span>'
                                    }
                                    if (lineUrlData && lineUrlData != '') {
                                        var urls = lineUrlData.split("#");
                                        if (urls && urls.length > 0) {
                                            urls.forEach(function (url, i) {
                                                var urlDatas = url.split("$");
                                                if(urlDatas && urlDatas.length > 1){
                                                    var urlName = urlDatas[0];
                                                    var urlLink = urlDatas[1];
                                                    var m3u8RegExpress = /m3u8$/i;
                                                    if (urlName && urlName != '' && urlLink && urlLink != '' && m3u8RegExpress.test(urlLink)){
                                                        if (newName && newName != "" && isNaN(newName) && mtype && mtype == 1){
                                                            urlName = newName;
                                                        }
                                                        var htmlId = "l-" + lineId + 'u-' + j + '-' + i;
                                                        urlHtml += "<div name='lineData' id='" + htmlId + "' udata='" + urlLink + "'>" + urlName + "</div>";
                                                    }
                                                }
                                            })

                                        }
                                    }
                                }
                            }

                            var lineHtml = '<li class="mar-top-10">' +
                                '<ul>' +
                                '<li class="line-name">' + lineName + '</li>' +
                                '<li class="line-res">' + urlHtml + '</li>' +
                                '</ul>' +
                                '</li>';
                            linesHtml += lineHtml;

                        });
                        $('#lineContent').html(linesHtml);

                        $("#lineContent div[name='lineData']").on("click", function () {
                            var curId = $(this).attr('id');
                            if (curId == curChoiceLine) {
                                return;
                            }
                            $("#lineContent div[name='lineData']").removeClass("active");
                            $(this).addClass("active");

                            var playUrl = $(this).attr('udata');


                            curChoiceLine = curId;
                            var playData =
                                {
                                    src: playUrl,
                                    type: 'application/x-mpegURL'
                                };

                            $("#ikanbot-player").removeClass('vjs-paused');
                            player.src(playData);
                            if (isFirstPlay){
                                isFirstPlay = false;
                            }else {
                                player.play();
                            }
                            if (!isMobileScreen){
                                $(window).scrollTop(150);
                            }
                            try {
                                let videoTitle = $("#video_title").text();
                                let lineName = $(this).text();
                                let nowTimestamp = new Date().getTime();
                                let saveHistoryData = {
                                    videoId:loadVideoId,
                                    lineId:curId,
                                    title:videoTitle,
                                    name:lineName,
                                    date:nowTimestamp
                                }
                                //console.log(saveHistoryData);
                                savePlayHistory(saveHistoryData);
                            }catch (e){
                                //do nothing
                            }

                        });
                        let historyV = getPlayHistory(loadVideoId);
                        if (historyV){
                            try {
                                if (historyV.lineId){
                                    $("#" + historyV.lineId).trigger("click");
                                }
                            }catch (e){}
                        }else {
                            $("#lineContent div[name='lineData']").first().trigger("click");
                        }
                    }else {
                        $('#lineContent').html("<li>目前没有找到可用线路</li>");
                    }
                }else {
                    var errorMsg = "";
                    if (respState == -401){
                        errorMsg = "获取数据失效，请强制刷新浏览器或者清除缓存后重新访问。"
                    }else {
                        errorMsg = "获取线路失败("+respState+")"
                    }
                    $('#lineContent').html("<li>"+errorMsg+"</li>");
                }
            },
            error:function (){
                $('#lineContent').html("<li>获取线路出错了,请强制刷新浏览器或者清除缓存后重新访问。(或者更换浏览器)</li>");
            }
        });
    }

});
function isWeixn(){
    const ua = navigator.userAgent.toLowerCase();
    let reg = /(micromessenger)/i;
    if (reg.test(ua)){
        return true;
    }else {
        return false;
    }
}
function savePlayHistory(saveData){
    let historyData = window.localStorage.getItem("playHistory");
    let history = null;
    if (historyData && historyData != ''){
        history = JSON.parse(historyData);
    }else {
        history = new Array();
    }
    let videoId = saveData.videoId;
    history = history.filter(function (obj){
        return obj.videoId != videoId;
    });
    history.unshift(saveData);
    if (history.length > 10){
        history = history.slice(0,10);
    }
    let saveLocalData = JSON.stringify(history);
    window.localStorage.setItem("playHistory",saveLocalData);
}
function getPlayHistory(videoId){
    let historyData = window.localStorage.getItem("playHistory");
    let history = null;
    if (historyData && historyData != ''){
        history = JSON.parse(historyData);
        history = history.filter(function (obj){
            return obj.videoId == videoId;
        });
        if (history && history.length > 0){
            return history[0];
        }
    }
    return null;

}