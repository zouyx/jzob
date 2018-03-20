---
layout: post
title: Golang-go_tool_pprof性能监控
permalink: /posts/2016/6/21/Golang-go_tool_pprof性能监控.html
---

什么是go tool pprof性能监控？怎么用？以下会为你一一解答，还会和java工具对比哦。

## Let's Go!
-----

## 1.结论

* Golang 自带工具监控cpu，内存比较简单，并提供可视化界面。
* 学习成本较低。
* 推荐使用。

## 2.是什么？

* 用于量化go语言性能而存在的分析工具
* 使用可视化工具来分析服务器运行时生成的预定格式数据
* 多种数据分析图
* golang package中自带的工具

## 3.有什么种类？

* Heap Profile: 内存堆栈图，用于分析内存使用率
* 30-second CPU profile: 30s内的cpu使用率，包括GC时间占比
* Goroutine Blocking Profile: goroutine的阻塞分析图，分析goroutine是否有泄漏
* 5-second executable trace: 收集5s 执行足迹

## 4.怎么用

### 启动

建立main方法并启动

``` go
package main

import (
	"net/http"
	_ "net/http/pprof"
)

func main() {
	go func() {
		http.ListenAndServe("0.0.0.0:6060",nil)
	}()
}
```

### 图形化工具 - graphviz

安装后，才能正常显示go的绘图，[下载地址](http://119.147.135.245/tech.down.sina.com.cn/20120204/a76dfa78/graphviz-2.28.0.msi?fn=&ssig=JqViplY8Zw&Expires=1465889507&KID=sae,230kw3wk15&ip=1465810307,125.88.149.36&corp=1)

### 应用

1. cmd line

* the heap profile : go tool pprof http://localhost:6060/debug/pprof/heap
* 30-second CPU profile : go tool pprof http://localhost:6060/debug/pprof/profile
* goroutine blocking profile : go tool pprof http://localhost:6060/debug/pprof/block

2. website

http://localhost:6060/debug/pprof

## 5.内存监控

### 模拟程序
1. 启动监控程序
2. 初始化并读取内存信息
3. 循环分配大内存
4. 再次读取内存信息
5. 通过makeMem分配大内存

如下图：

![memMock](/images/gopprof/memMock.png)

### 结果

![memMock](/images/gopprof/memResult.png)

其中包含：内存分配信息 与 统计基本信息

#### 如何阅读
* 从上到下，最顶端为入口
* 方框：大：占用时间／资源比较多，小则与之相反
* 线条：粗：占用时间／资源比较多，小则与之相反
* 立方体：占用并没有释放的内存

## 6.cpu监控

### 模拟程序
1. 监听监控端口
2. goroutine斐波拉契数列
3. 运行斐波拉契数列

如下图：

![cpuMock](/images/gopprof/cpuMock.png)

### 结果

![cpuResult](/images/gopprof/cpuResult.png)

其中包含：

* 占用cpu时间
* 调用链路
* 统计时长
* runtime.morestack：申请栈空间

## 7.与java对比


| 对比项        | Golang           | Java  |
| :-------------: |:-------------:| :-----:|
| 性能工具     | 自带      |    部分自带 |
| GC信息      | 设置环境变量并重启程序 | 直接通过命令／打gc.log |
| 堆栈信息     | 侵入／清晰      |   非侵入／清晰 |
| CPU信息     | 查看成本／要求较低      |  查看成本／要求较高   |


## 8.更多命令
> [http://wiki.jikexueyuan.com/project/go-command-tutorial/0.12.html](http://wiki.jikexueyuan.com/project/go-command-tutorial/0.12.html)

## 9.参考资料
> [http://studygolang.com/articles/2110](http://studygolang.com/articles/2110)
> [https://segmentfault.com/a/1190000000501635](https://segmentfault.com/a/1190000000501635)
> [http://www.cnblogs.com/yjf512/archive/2012/12/27/2835331.html](http://www.cnblogs.com/yjf512/archive/2012/12/27/2835331.html)
