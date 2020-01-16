---
layout: post
title: dubbo-go实现丝滑的应用配置
permalink: /posts/2020/01/17/dubbo-go丝滑的应用配置.html
---

dubbo-go丝滑的应用配置

# Let‘s Go!
-----

之前在Apache/dubbo-go（以下简称dubbo-go）中实现了基于Apollo实现应用级配置管理的功能。但实现当时，并不了解整体项目架构，也花了不少时间了解。

dubbo是基于各种开源配置中心实现丝滑的应用配置，包括：
* [Apollo](https://github.com/ctripcorp/apollo)
* [zookeeper](https://github.com/apache/zookeeper)
* [nacos](https://github.com/alibaba/nacos)

基于动态的插件机制在启动时按需加载，达到丝滑配置应用配置的目的。

那在dubbo-go中究竟怎么实现呢？

实现该部分功能放置于一个独立的子项目中，见：[https://github.com/apache/dubbo-go/tree/master/config_center](https://github.com/apache/dubbo-go/tree/master/config_center)

## 总体设计

[![configCenterClass](/images/dubbogo/configcenter/configcenter-class.jpg)](/images/dubbogo/configcenter/configcenter-class.jpg)

主要作用于以下两个阶段

* 初始化程序阶段：加载对应的配置中心插件。

* 启动阶段：读取并解析本地配置文件中配置中心信息。初始化配置中心链接，监听数据变更等。

### ConfigCenterFactory

使用者加载对应配置中心模块后，在初始化阶段加入各配置中心模块往其中注册其初始化类。

[![configCenterFactory](/images/dubbogo/configcenter/configCenterFactory.png)](/images/dubbogo/configcenter/configCenterFactory.png)


### DynamicConfigurationFactory

整个动态配置中心的关键点就在DynamicConfigurationFactory上，其中通过解析内部自定义的URL，获取其协议类型，反射其参数，用于创建配置中心的链接。

[![configurationFactory](/images/dubbogo/configcenter/configurationFactory.png)](/images/dubbogo/configcenter/configurationFactory.png)

如：

配置文件中配置
```
config_center:
  protocol: apollo
  address: 10.1.22.33:8080
  app_id: test
  cluster: dev
```

dubbo-go内部会解析为
```
apollo://10.1.22.33:8080?app_id=test&cluster=dev
```
在内部传递，用于初始化配置中心链接。

**PS**：在dubbo-go中到处可见这种内部协议，透彻理解这个内部协议对阅读dubbo-go代码很有帮助。

### DynamicConfiguration

该接口规定了各个配置中心需要实现的功能：
* 配置数据反序列化方式：目前只有properties反序列化，参见：DefaultConfigurationParser
* 增加监听器：用于增加监听数据变化后增加特定逻辑（受限于配置中心client端实现）
* 删除监听器：删除已有监听器（受限于配置中心client端实现，目前所致nacos没有提供该方法）
* 获取路由配置：获取路由表配置。
* 获取应用级配置：获取应用层级配置，如：协议类型配置等

等

[![dynamicConfiguration](/images/dubbogo/configcenter/dynamicConfiguration.png)](/images/dubbogo/configcenter/dynamicConfiguration.png)


## 总结

整个配置中心的功能，麻雀虽小，但五脏俱全。目前并不算是十分完善，但是整个框架层面上来说，是走在了正确的路上。从扩展性来说，是比较便利。目前支持的配置中心还不够丰富，只有zookeeper与apollo，支持的配置文件格式也只有properties，虽然能满足基本使用场景，距离完善还有还长远的路。

未来计划：

1. nacos（已有pr，正在review）
2. etcd（未支持）
3. consul（未支持）
4. 丰富的文件配置格式，如：yml。xml等。