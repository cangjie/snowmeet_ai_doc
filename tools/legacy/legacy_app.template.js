// 旧版演示（legacy 分包）的「App」。
// 由 snowmeet_ai_doc/tools/legacy/build_legacy.py 生成，来源 snowmeet_wechat_mini@__OLD_REV__（origin/master），不要手改。
//
// 代替旧版 app.js：legacy/ 下的页面和组件原来调用 getApp() 的地方都改成用本模块，
// 因此旧版的域名、登录态与新版的 getApp().globalData 完全隔离（旧版连 __DEMO_DOMAIN__）。
// 本模块只读新版的登录信息（判断是否管理员），不写新版的任何状态、storage 或文件。
//
// 旧版用到的全局资源（蓝牙、WebSocket、键盘监听、定时器）都经 lwx 记账，
// 「返回新版」时只释放旧版自己占用的那部分，避免带到新版里。

var app = module.exports   // 本模块不 require 任何文件

var DOMAIN = '__DEMO_DOMAIN__'

app.globalData = {
  appId: 'wxd1310896f2aa68bb',
  domainName: DOMAIN,
  requestPrefix: 'https://' + DOMAIN + '/api/',
  uploadDomain: DOMAIN,
  userInfo: null,
  sessionKey: '',
  cellNumber: '',
  role: '',
  isWebsocketOpen: false,
  scene: (function () {
    try { return wx.getLaunchOptionsSync().scene } catch (e) { return '' }
  })(),
  adminTabbarItem: [
    {
      "text": "养护",
      "iconPath": "/legacy/images/icons/icon_maintain_white.jpg",
      "selectedIconPath": "/legacy/images/icons/icon_maintain_white.jpg",
      "pagePath": "/legacy/pages/admin/equip_maintain/search_order/search_order"
    },
    {
      "text": "订单",
      "iconPath": "images/zhihu-fill.png",
      "selectedIconPath": "images/zhihu-fill-hl.png",
      "pagePath": "/legacy/pages/test/upload/upload"
    },
    {
      "pagePath": "/legacy/pages/admin/equip_maintain/uploadimage/uploadimage",
      "text": "上传测试"
    },
    {
      "pagePath": "/legacy/pages/admin/equip_maintain/uploadimage/uploadimage",
      "text": "上传测试"
    }
  ],
  userTabBarItem: [
    {
      "pagePath": "/legacy/pages/ski_pass/ski_pass_selector",
      "text": "预定"
    },
    {
      "pagePath": "/legacy/pages/mine/mine",
      "text": "我的"
    }
  ]
}

// 旧版 env 页面切换域名用；演示固定连 DOMAIN，不读写 domain.txt
app.getDomain = function () {
  return DOMAIN
}
app.setDomain = function (domain) {
  console.log('[legacy] 演示版固定连 ' + DOMAIN + '，忽略切换域名', domain)
}

// ---- 全局资源记账 ----
var bleAdapterOpened = false
var bleDiscovering = false
var bleDevices = {}
var keyboardListeners = []
var sockets = []
var intervals = {}
var timeouts = {}

function wrapSuccess(opts, onSuccess) {
  opts = opts || {}
  if (!opts.success && !opts.fail && !opts.complete) {
    // Promise 风格调用：原样返回 Promise，成功时记账
    var p = null
    return { opts: opts, promise: function (call) {
      p = call(opts)
      if (p && p.then) {
        p.then(function (res) { onSuccess(res) }, function () {})
      }
      return p
    } }
  }
  var success = opts.success
  opts.success = function (res) {
    onSuccess(res)
    if (success) {
      return success.apply(this, arguments)
    }
  }
  return { opts: opts, promise: null }
}

function callTracked(api, opts, onSuccess) {
  var w = wrapSuccess(opts, onSuccess)
  if (w.promise) {
    return w.promise(function (o) { return wx[api](o) })
  }
  return wx[api](w.opts)
}

app.lwx = {
  openBluetoothAdapter: function (opts) {
    return callTracked('openBluetoothAdapter', opts, function () { bleAdapterOpened = true })
  },
  startBluetoothDevicesDiscovery: function (opts) {
    return callTracked('startBluetoothDevicesDiscovery', opts, function () { bleDiscovering = true })
  },
  createBLEConnection: function (opts) {
    var deviceId = opts && opts.deviceId
    return callTracked('createBLEConnection', opts, function () {
      if (deviceId) {
        bleDevices[deviceId] = true
      }
    })
  },
  onKeyboardHeightChange: function (listener) {
    keyboardListeners.push(listener)
    return wx.onKeyboardHeightChange(listener)
  },
  connectSocket: function (opts) {
    var task = wx.connectSocket(opts)
    if (task) {
      sockets.push(task)
    }
    return task
  },
  setInterval: function () {
    var id = setInterval.apply(null, arguments)
    intervals[id] = true
    return id
  },
  setTimeout: function (fn) {
    var args = Array.prototype.slice.call(arguments)
    var id = null
    if (typeof fn === 'function') {
      args[0] = function () {
        delete timeouts[id]
        return fn.apply(this, arguments)
      }
    }
    id = setTimeout.apply(null, args)
    timeouts[id] = true
    return id
  }
}

function releaseResources(done) {
  Object.keys(intervals).forEach(function (id) { try { clearInterval(Number(id)) } catch (e) {} })
  Object.keys(timeouts).forEach(function (id) { try { clearTimeout(Number(id)) } catch (e) {} })
  intervals = {}
  timeouts = {}
  keyboardListeners.forEach(function (fn) { try { wx.offKeyboardHeightChange(fn) } catch (e) {} })
  keyboardListeners = []
  sockets.forEach(function (task) { try { task.close({}) } catch (e) {} })
  sockets = []
  Object.keys(bleDevices).forEach(function (deviceId) {
    try { wx.closeBLEConnection({ deviceId: deviceId }) } catch (e) {}
  })
  bleDevices = {}
  if (bleDiscovering) {
    try { wx.stopBluetoothDevicesDiscovery({}) } catch (e) {}
    bleDiscovering = false
  }
  if (bleAdapterOpened) {
    bleAdapterOpened = false
    try {
      wx.closeBluetoothAdapter({ complete: function () { done() } })
      return
    }
    catch (e) {}
  }
  done()
}

// 「返回新版」：释放旧版占用的资源，回到新版后台首页
app.exitToNew = function () {
  releaseResources(function () {
    wx.reLaunch({ url: '/pages/admin/admin' })
  })
}

// 只读新版登录信息：不是管理员就回新版首页（防止从搜索、分享、扫码进入演示）
function guardAdmin() {
  var newApp = null
  try { newApp = getApp() } catch (e) {}
  if (!newApp || !newApp.loginPromiseNew) {
    return
  }
  newApp.loginPromiseNew.then(function () {
    var staff = newApp.globalData && newApp.globalData.staff
    if (!(staff && staff.title_level > 200)) {
      releaseResources(function () {
        wx.reLaunch({ url: '/pages/index/index' })
      })
    }
  })
}

// legacy/ 下所有页面的 Page() 都经过这里
app.Page = function (options) {
  options = options || {}
  var onShow = options.onShow
  options.onShow = function () {
    try {
      if (wx.hideHomeButton) {
        wx.hideHomeButton()
      }
    }
    catch (e) {}
    guardAdmin()
    if (onShow) {
      return onShow.apply(this, arguments)
    }
  }
  options.__legacyExit = function () {
    app.exitToNew()
  }
  return Page(options)
}

// 同旧版 utils/util.js 的 performWebRequest（内联一份，避免本模块与 utils/util.js 互相 require）
function performWebRequest(url, data) {
  return new Promise(function (resolve, reject) {
    wx.request({
      url: url,
      data: data,
      method: data == undefined ? 'GET' : 'POST',
      success: function (res) {
        if (res.statusCode != 200) {
          wx.showToast({ title: res.statusCode.toString(), icon: 'error' })
          return
        }
        if (res.data.code != 0) {
          if (res.data.message != '') {
            wx.showToast({ title: res.data.message, icon: 'none' })
          }
          reject(res.data.message)
        }
        else {
          resolve(res.data.data)
        }
      },
      fail: function () {
        wx.showToast({ title: '网络不通', icon: 'error' })
        reject({})
      }
    })
  })
}

// 旧版登录：连演示服务器，登录态只存在本模块
app.loginPromiseNew = new Promise(function (resolve) {
  wx.login({
    success: function (res) {
      var fontUrl = 'https://' + app.globalData.domainName + '/font/thin.ttf'
      wx.loadFontFace({
        family: 'icon-font',
        source: 'url("' + fontUrl + '")',
        success: function () {},
        fail: function () {}
      })
      try {
        app.globalData.env = wx.getAccountInfoSync().miniProgram.envVersion || 'trail'
      }
      catch (e) {
        app.globalData.env = 'trail'
      }
      var url = 'https://' + app.globalData.domainName + '/api/MiniAppHelper/MemberLogin?code=' + res.code + '&openIdType=' + encodeURIComponent('wechat_mini_openid')
      performWebRequest(url, undefined).then(function (session) {
        app.globalData.sessionKey = encodeURIComponent(session.session_key)
        app.globalData.member = session.member
        app.globalData.staff = session.staff
        app.globalData.deviceInfo = wx.getDeviceInfo()
        app.globalData.windowInfo = wx.getWindowInfo()
        app.globalData.appBaseInfo = wx.getAppBaseInfo()
        wx.getSystemInfoAsync({
          success: function (info) {
            app.globalData.systemInfo = info
          },
          fail: function () {
            try {
              app.globalData.systemInfo = wx.getSystemInfoSync()
            }
            catch (e) {}
          },
          complete: function () {
            resolve({})
          }
        })
      })
    },
    fail: function (res) {
      console.log('[legacy] wx.login fail', res)
    }
  })
})
