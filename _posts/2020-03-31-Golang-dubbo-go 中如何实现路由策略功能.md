---
layout: post
title: dubbo-go 中如何实现路由策略功能
permalink: /posts/2020/03/30/dubbo-go 中如何实现路由策略功能.html
---

dubbo-go 中如何实现路由策略功能

# Let‘s Go!
-----

最近在 Apache/dubbo-go（以下简称 dubbo-go ）社区中，路由策略突然成了呼声最高的功能之一。那到底为什么需要路由策略？

先路由策略需要实现的功能：

路由策略（ routing policy）是为了改变网络流量所经过的途径而修改路由信息的技术，主要通过改变路由属性（包括可达性）来实现。

试想该下场景：使用 dubbo-go 在生产环境上，排除预发布机。使用路由策略实现不是很合适吗？

虽然知道了路由策略需要实现什么功能，但还不足以实现一个完整的路由策略功能。除此之外，还需要知道如何方便的管理路由策略。

# 目标

综上所述，可以总结出以下 **目标**

* 支持方便扩展路由策略的配置；
* 可以方便的管理路由策略配置，如支持本地与远程配置中心管理；
* 与 Dubbo 现有的配置中心内的路由策略配置文件兼容，降低在新增语言栈的学习及使用成本；

# 路由策略设计

在设计之初，首先要考虑的是路由策略应该放在整个服务治理周期的哪个阶段呢？

有些读者可能会有点困惑，我连架构图都不知道，如何考虑在哪个阶段？不怕，下图马上给你解惑。

![dubbo-go-arch.png](/images/dubbogo/router/dubbo-go-arch.png)

可以看到图中的 Router 就是路由策略插入的位置，目前路由策略主要用于控制 Consumer 到 Provider 之间的网络流量的路由路径。

除此之外，还有几个问题是需要优先考虑：

1.需要设计什么接口？如何设计接口？为什么要这么设计接口？



2.如何实现本地与远程路由策略配置加载？

* 本地路由策略配置：在原配置加载阶段，新增读取路由配置文件。使用 ```FIleRouterFactory``` 解析后，生成对应路由策略，放置到内存中备用。
* 远程路由策略配置：在 zookeeper 注册并监听静态资源目录后。读取静态资源，筛选符合路由策略配置信息，通过 ```RouterFactory``` 生成对应路由策略，放置到内存中备用。


## Router
通过使用本实例路由策略匹配远程实例的路由策略。
![router.png](/images/dubbogo/router/router.png)


## RouterChain
执行多个路由策略的责任链。
![router-chain.png](/images/dubbogo/router/router-chain.png)

## FIleRouterFactory
生成解析配置文件生成路由策略的工厂类。
![file-router-factory.png](/images/dubbogo/router/file-router-factory.png)

## RouterFactory
生成读取远程配置中心生成路由侧露的工厂类。
![router-factory.png](/images/dubbogo/router/router-factory.png)