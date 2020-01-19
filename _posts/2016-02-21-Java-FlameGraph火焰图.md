---
layout: post
title: Java-FlameGraph火焰图
published: true
permalink: /posts/2016/2/21/Java-FlameGraph火焰图.html
category: public
---

什么是FlameGraph火焰图？怎么用？以下会为你一一解答。

## Let's Go!
-----

## 1.结论

* 如果能生成出来对应图表，分析java使用cpu性能很好用。
* 但是有时生成出来的堆栈写着Unknown，没有具体堆栈信息，会比较抓狂。
如想获取更多信息请参考：[https://github.com/jvm-profiling-tools/perf-map-agent/issues/44](https://github.com/jvm-profiling-tools/perf-map-agent/issues/44)
* Github提问题回复速度也较慢，遇到自己解决不了的问题也会比较头疼。

## 2.是什么？

用于量化框架中的性能，包括代码编译消耗的时间，代码缓存，其他系统类库及内核代码执行的时间，常用于定位cpu使用率问题。

## 3.有什么种类？

* [red/blue differential flame graphs](http://www.brendangregg.com/blog/images/2014/zfs-flamegraph-diff.svg)
* [flame graph](http://www.brendangregg.com/blog/images/2014/zfs-flamegraph-after.svg)
* [CPI（cycles-per-instruction）flame graph](http://www.brendangregg.com/blog/2014-10-31/cpi-flame-graphs.html):CPI(平均每条指令的平均时钟周期数)=(cpu时间/ic指令数目)*频率

## 4.怎么样？

![flamegraph](/images/FlameGraph/flamegraph.png)

## 5.安装及应用呢？

[FlameGraph介绍](https://github.com/brendangregg/FlameGraph)

[安装及应用步骤](http://techblog.netflix.com/2015/07/java-in-flames.html)

### 环境要求（重要）

* 操作系统centos 7.0
* cmake2.8.6或以上
* JDK8 update 60 build 19 以后，需要添加jdk启动参数：-XX:+PreserveFramePointer
* 安装perf

## 6.怎么看？

![how](/images/FlameGraph/howtoread.png)

### 图表
* y轴：栈深度
* x轴：cpu时间
* 长方形：一个栈（方法）
* 长度：出现在监视器中的时长（占用cpu的时间）
* 其他：从左到右的顺序只是按字母排序，无其他意义

### 分析
* 从下到上：从父到子方法追查方法
* 从上到下：先找出占用最多时间的栈，找出它的进程，在图最底部，关注最宽的方法。

### 工具包
* perf_events:标准linux分析器，用于生成系统堆栈信息
* perf-map-agent:提供转换perf_events成带java标示的JVMTI代理
* Flame Graph:生成火焰图的工具
* Misc:生成全部java进程的堆栈信息

## 7.还有一些问题

* 很多java方法都是缺少的，对比起jstack，在图里的堆栈信息可能只有1／3的深度。 
* JVM动态编译（JIT）时不会暴露一个图表给系统监视器（已修复）
* JVM还使用x86上的帧指针寄存器(RBP在x86 - 64)作为一个通用寄存器
