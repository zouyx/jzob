---
layout: post
title: dubbo-go 实现丝滑的应用配置
permalink: /posts/2020/01/17/dubbo-go 丝滑的应用配置.html
category: private
---

dubbo-go 丝滑的应用配置

# Let‘s Go!
-----

之前在 Apache/dubbo-go（以下简称 dubbo-go ）中实现应用级配置管理的功能。但实现当时，并不了解整体项目架构，也花了不少时间了解。

dubbo 是基于各种开源配置中心实现丝滑的应用配置，包括：

* [Apollo](https://github.com/ctripcorp/apollo) ：携程框架部门研发的分布式配置中心，能够集中化管理应用不同环境、不同集群的配置，配置修改后能够实时推送到应用端，并且具备规范的权限、流程治理等特性，适用于微服务配置管理场景。
* [zookeeper](https://github.com/apache/zookeeper) ：一个分布式的，开放源码的分布式应用程序协调服务，是 Google 的 Chubby 一个开源的实现，是 Hadoop 和 Hbase 的重要组件。它是一个为分布式应用提供一致性服务的软件，提供的功能包括：配置维护、域名服务、分布式同步、组服务等。
* [nacos](https://github.com/alibaba/nacos) : Alibaba 开源的配置管理组件，提供了一组简单易用的特性集，帮助您实现动态服务发现、服务配置管理、服务及流量管理。

配置中心在 dubbo-go 中主要承担以下场景的职责：

* 作为外部化配置中心，即存储 dubbo.properties 配置文件，此时，key 值通常为文件名如 dubbo.properties , value 则为配置文件内容。
* 存储单个配置项，如各种开关项、常量值等。
* 存储服务治理规则，此时 key 通常按照 “服务名 + 规则类型” 的格式来组织，而 value 则为具体的治理规则。

基于动态的插件机制在启动时按需加载，达到丝滑配置应用配置的目的。

那在 dubbo-go 中究竟怎么实现呢？

实现该部分功能放置于一个独立的子项目中，见：[https://github.com/apache/dubbo-go/tree/master/config_center](https://github.com/apache/dubbo-go/tree/master/config_center)

## 使用方法

在 Go 里面，使用方法如下：

[![zookeeper-usercase](/images/dubbogo/configcenter/zookeeper-usercase.png)](/images/dubbogo/configcenter/zookeeper-usercase.png)

使用配置中心并不复杂。

#### 加载插件
* zookeeper
```golang
_ "github.com/apache/dubbo-go/config_center/zookeeper"
```
* Apollo
```golang
_ "github.com/apache/dubbo-go/config_center/apollo"
```

#### 增加配置文件

* zookeeper

```
config_center:
  protocol: "zookeeper"
  address: "127.0.0.1:2181"
```

* Apollo

如果需要使用 Apollo 作为配置中心，请提前创建 namespace : dubbo.properties ，用于配置管理。
```
config_center:
  protocol: "apollo"
  address: "127.0.0.1:8070"
  app_id: test_app
  cluster: dev
```


## 整体设计

[![design](/images/dubbogo/configcenter/design.jpg)](/images/dubbogo/configcenter/design.jpg)

优先考虑与现有 dubbo 设计兼容，dubbo 是基于 [dubbo-admin](https://github.com/apache/dubbo-admin) 实现应用级配置管理，以 zookeeper 为例，对服务提供者与服务消费者进行整体流程分析。

### 配置管理

**dubbo-admin** 配置管理中增加 global 配置，zookeeper 中会自动生成其对应配置节点，内容均为 **dubbo-admin** 中设置的配置。

* /dubbo/config/dubbo/dubbo.properties 对应全局配置文件。
* /dubbo/config/dubbo/ 应用名 /dubbo.properties 对应指定应用配置文件。

#### 节点路径

[![key-struct](/images/dubbogo/configcenter/key-struct.jpg)](/images/dubbogo/configcenter/key-struct.jpg)

上图展示了 dubbo.properties 文件在 zookeeper 和 Apollo 中的存储结构：

**zookeeper**

* 命名空间 namespace 都为： dubbo

* 分组 group ：全局级别为 dubbo , 所有应用共享；应用级别为应用名 demo-provider ，只对该应用生效

* key : dubbo.properties

**Apollo**

* app_id : 自由指定，默认： dubbo ，最好与 zookeeper  namespace 一致

* cluster : 自由指定，最好与 zookeeper group 一致

* 命名空间 namespace : dubbo.properties

zookeeper 与 Apollo 最大的不一样就在于 dubbo.properties 所在的节点。


## dubbo-go设计

[![configCenterClass](/images/dubbogo/configcenter/configcenter-class.jpg)](/images/dubbogo/configcenter/configcenter-class.jpg)


### 流程说明

主要作用于以下两个阶段

* 初始化程序阶段：加载对应的配置中心所需的插件。

* 启动阶段：读取并解析本地配置文件中配置中心信息。初始化配置中心链接，读取 /dubbo/config/dubbo/dubbo.properties 与 /dubbo/config/dubbo/应用名/dubbo.properties ，并将其加载到内存之中，监听其变更，实时更新至内存。

### ConfigCenterFactory

使用者加载对应配置中心模块后，在初始化阶段加入各配置中心模块往其中注册其初始化类。

[![configCenterFactory](/images/dubbogo/configcenter/configCenterFactory.png)](/images/dubbogo/configcenter/configCenterFactory.png)


### DynamicConfigurationFactory

整个动态配置中心的关键点就在 DynamicConfigurationFactory 上，其中通过解析内部自定义的 URL ，获取其协议类型，反射其参数，用于创建配置中心的链接。

[![configurationFactory](/images/dubbogo/configcenter/configurationFactory.png)](/images/dubbogo/configcenter/configurationFactory.png)

如：

配置文件中配置
```
config_center:
  protocol: zookeeper
  address: 127.0.0.1:2181
  namespace: test
```

dubbo-go 内部会解析为
```
zookeeper://127.0.0.1:2181?namespace=test
```
在内部传递，用于初始化配置中心链接。

**PS**：在 dubbo-go 中到处可见这种内部协议，透彻理解这个内部协议对阅读 dubbo-go 代码很有帮助。

### DynamicConfiguration

该接口规定了各个配置中心需要实现的功能：
* 配置数据反序列化方式：目前只有 properties 反序列化，参见： DefaultConfigurationParser 。
* 增加监听器：用于增加监听数据变化后增加特定逻辑（受限于配置中心 client 端实现）。
* 删除监听器：删除已有监听器（受限于配置中心 client 端实现，目前所知 nacos client 没有提供该方法）。
* 获取路由配置：获取路由表配置。
* 获取应用级配置：获取应用层级配置，如：协议类型配置等。

[![dynamicConfiguration](/images/dubbogo/configcenter/dynamicConfiguration.png)](/images/dubbogo/configcenter/dynamicConfiguration.png)


## 总结

更加具体的实现，我就不详细论述，大家可以去看源码，欢迎大家持续关注，或者贡献代码。

整个配置中心的功能，麻雀虽小，但五脏俱全。目前并不算是十分完善，但是整个框架层面上来说，是走在了正确的路上。从扩展性来说，是比较便利。目前支持的配置中心还不够丰富，只有 zookeeper 与 Apollo ，支持的配置文件格式也只有 properties ，虽然能满足基本使用场景，距离完善还有还长远的路。

未来计划：

1. nacos（已有 PR , 正在 review ）
2. etcd（未支持）
3. consul（未支持）
4. 丰富的文件配置格式，如： yml , xml 等
