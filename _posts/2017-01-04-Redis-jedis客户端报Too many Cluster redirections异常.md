---
layout: post
title: Redis-jedis客户端报Too many Cluster redirections异常
permalink: /posts/2017/1/4/Redis-jedis客户端报Too many Cluster redirections异常.html
---

jedis客户端报Too many Cluster redirections异常？很困扰？不知道是什么问题？请看以下文章，为你一一解答。

## Let's Go!
-----

## 1.解决方案

* 暂没发现比较好的解决方案。

## 2.环境

* Redis 3.x Cluster
* Jedis 2.8
* Jdk1.8

## 3.场景


## 4.问题现象

请求间歇性穿透缓存。

### 错误信息

```
redis.clients.jedis.exceptions.JedisClusterMaxRedirectionsException: Too many Cluster redirections?
    at redis.clients.jedis.JedisClusterCommand.runWithRetries(JedisClusterCommand.java:34)
    at redis.clients.jedis.JedisClusterCommand.runWithRetries(JedisClusterCommand.java:85)
    at redis.clients.jedis.JedisClusterCommand.runWithRetries(JedisClusterCommand.java:68)
    at redis.clients.jedis.JedisClusterCommand.runWithRetries(JedisClusterCommand.java:85)
    at redis.clients.jedis.JedisClusterCommand.runWithRetries(JedisClusterCommand.java:68)
    at redis.clients.jedis.JedisClusterCommand.runWithRetries(JedisClusterCommand.java:85)
    at redis.clients.jedis.JedisClusterCommand.runWithRetries(JedisClusterCommand.java:68)
    at redis.clients.jedis.JedisClusterCommand.run(JedisClusterCommand.java:29)
    at redis.clients.jedis.JedisCluster.set(JedisCluster.java:75)
 ```

## 5.问题原因

通过分析以下代码得知错误原因：

``` java
private T runWithRetries(byte[] key, int redirections, boolean tryRandomNode, boolean asking) {
    if (redirections <= 0) {
      throw new JedisClusterMaxRedirectionsException("Too many Cluster redirections?");
    }

    Jedis connection = null;
    try {

      if (asking) {
        // TODO: Pipeline asking with the original command to make it
        // faster....
        connection = askConnection.get();
        connection.asking();

        // if asking success, reset asking flag
        asking = false;
      } else {
        if (tryRandomNode) {
          connection = connectionHandler.getConnection();
        } else {
          connection = connectionHandler.getConnectionFromSlot(JedisClusterCRC16.getSlot(key));
        }
      }

      return execute(connection);
    } catch (JedisConnectionException jce) {
      if (tryRandomNode) {
        // maybe all connection is down
        throw jce;
      }

      // release current connection before recursion
      releaseConnection(connection);
      connection = null;

      // retry with random connection
      return runWithRetries(key, redirections - 1, true, asking);
    } catch (JedisRedirectionException jre) {
      // if MOVED redirection occurred,
      if (jre instanceof JedisMovedDataException) {
        // it rebuilds cluster's slot cache
        // recommended by Redis cluster specification
        this.connectionHandler.renewSlotCache(connection);
      }

      // release current connection before recursion or renewing
      releaseConnection(connection);
      connection = null;

      if (jre instanceof JedisAskDataException) {
        asking = true;
        askConnection.set(this.connectionHandler.getConnectionFromNode(jre.getTargetNode()));
      } else if (jre instanceof JedisMovedDataException) {
      } else {
        throw new JedisClusterException(jre);
      }

      return runWithRetries(key, redirections - 1, false, asking);
    } finally {
      releaseConnection(connection);
    }
  }
```

当发生JedisConnectionException或者JedisRedirectionException时，会重新调用当前方法。

### JedisConnectionException

与该错误关系不大。

因为该错误是：连接Redis错误，如果连接第一个节点失败，尝试第二个节点也失败，会直接推断成全部节点down掉抛出错误，中断处理。

### JedisRedirectionException

和该错误关系很大。

对该错误处理时，并处理了以下两个异常：
JedisMovedDataException：节点重置／迁移后，会抛出该异常
JedisAskDataException： 数据迁移，发生asking问题, 获取asking的Jedis

从此推断，发生该问题的原因为：
1. 节点主从切换／迁移后，客户端与redis的slot不一致导致一直重试
2. asking 一直失败，当槽点数值分布在两个节点上时，容易引起该错误

因此，导致该错误的原因可为：
1. 节点主从切换／迁移后，网络等各种原因导致更新slot信息失败
2. asking时一直指向同一个节点，导致asking一直失败（该几率较少？）


