---
layout: post
title: Golang-Thrift请求后HttpStatus413
permalink: /posts/2016/7/21/Golang-Thrift请求后HttpStatus413.html
---

Thrift请求后得到HttpStatus413是什么鬼？以下会为你一一解答。

## Let's Go!
-----

## 1.解决方案

* 自己继承后重新实现（推荐）
* 修改thrfit包中SetHeader／Flush方法，增加重置header逻辑
* 每次都重新创建Thrift连接

## 2.环境

* Golang version：1.5
* Linux version：Linux version 2.6.32-279.el6.x86_64 (gcc version 4.4.6 20120305 (Red Hat 4.4.6-4) (GCC) ) 
* Os version：CentOS release 6.3 (Final) 2.6.32-279.el6.x86_64
* Cpu ：12
* Mem ：8G
* 网络协议：Thrift

## 3.场景
* 使用Sync.pool管理调用Thrift的goroutine，减少创建及销毁goroutine开销，c为调用client
``` go
    c := pool.Get()
	defer pool.Put(c)
    以下为调用逻辑....
```

## 4.问题现象

### 错误信息

* Client端报Http Status 413
* Server端无报错信息


## 5.问题原因
1.HttpStatus 413是什么意思？
> HTTP Status 413 （请求实体过大） 
> 服务器无法处理请求，因为请求实体过大，超出服务器的处理能力。

**注意：这里请求实体过大的意思是包括header和body（一开始定位时只定位了body，就进坑了- -）**

针对该问题主要为header过大

2.RPC时会设置header，但对于存在于pool中的goroutine，是Addheader，请看以下代码，

``` go
// Set the HTTP Header for this specific Thrift Transport
// It is important that you first assert the TTransport as a THttpClient type
// like so:
//
// httpTrans := trans.(THttpClient)
// httpTrans.SetHeader("User-Agent","Thrift Client 1.0")
func (p *THttpClient) SetHeader(key string, value string) {
	p.header.Add(key, value)
}
```

**这就是导致出现413的原因**
