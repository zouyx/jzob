---
layout: post
title: Golang-第一个Go程序-IDE
permalink: /posts/2013/5/21/Golang-第一个Go程序-IDE.html
---

解决Go文件不可执行的问题

# Let‘s Go!
-----
## 创建Go Project

## 目录结构

在一个Go Project目录下，有三个文件夹：bin、pkg、src，其中我们只需关注bin文件夹和src文件夹即可。bin文件夹是编译好的源文件所放置的 位置，也就是可执行文件的所在；而src就是源文件目录。

![1](/images/firstgoide/1.png)

## main.go

在src包下创建一个main包(一定要是main包),在main包下面创建go文件
键入

```go
package main

import (
 "fmt"
)

func main(){
  fmt.Printf("Hello World2")
}
```


## 执行

保存后就会自动在bin文件夹中生成.exe的可执行文件,这时程序才真正可执行

![2](/images/firstgo/2.png)

## 运行结果

![3](/images/firstgo/3.png)
