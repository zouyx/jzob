---
layout: post
title: Golang-Array-Slice-Map
permalink: /posts/2013/6/10/Golang-Array-Slice-Map.html
---

介绍Go三种数组结构

# Let‘s Go!
-----
## Array
   Array(数组)是固定长度,相同类型的集合,因为是固定长度,因此大小不能改变.
     
     1.1.创建Array
     有两种初始化方式
          1.1.1.固定长度
               var a [3]int
          
          1.1.2.自动统计长度
               var a [...]int{1,2,3}
               中括号用...代替长度值,就会自动元素个数并赋值长度

## Slice
   Slice(切片)是非固定长度,相同类型的集合,如果有新元素加入,Slice会增加长度,并且Slice总是指向一个底层的Array,是一个指向Array的指针

     2.1.创建一个长度为10,空的Slice
          slice:=make([]int,10)
     
     2.2.创建一个非空的slice
          slice:=[]int{1,2,3}
          注意:这里很容易搞错,上面是slice,下面是array
          slice:=[...]int{1,2,3}

          差别就是在于中括号中的数字,有数字就是array,没有就是slice
     
     2.3.创建一个Array,并且初始化Slice
          var a [...]int{1,2,3}
          slice:=[1:3]
     
     各种例子
 a:=[...]int{1,2,3,4,5}
 //从数组a中取出大于2,小于等于4的数字
 s1:=a[2:4]

 //从数组a中取出大于1,小于等于5的数字
 s2:=a[1:5]

 //用a中所有元素创建slice,这是a[0:len(a)]的简化写法
 s3:=a[:]

 //从序号0到3创建,这是a[0:4]简化写法,得到1,2,3,4
 s4:=a[:4]

 //从s2创建slice,注意s5的指针扔向指向a
 s5:=s2[:]

       2.4.追加slice元素
 s0:=[]int{1,2}
 //向s0中追加元素3
 s1:=append(s0,3)
 //向s0中追加多个元素
 s2:=append(s0,3,4,5)
 //向S0中追加一个slice
 s3:=append(s0,s2...)

       2.5.复制slice元素
        a:=[...]int{1,2,3,4,5}

 var s1=make([]int,6)
  //copy(target,src),src:源数组,target目标数组,返回函数是复制了多少个元素
 s2:=copy(s1,a[0:])
 println("s2",s2);

## Map

     Map可以理解为是一个有索引的数组,一般定义形式为map[from type(key type)]to type(value type)
     monthDays:= map[ string] int {
        "Jan" :31,"Feb" :30,"Mar" :31,
        "Apr" :30,"May" :30,"Jun" :30,//<<<<<最后这个逗号是必须的!
     }
     3.1.读取
     println( "May:" ,monthDays["May" ]);

     3.2.增加元素
     monthDays[ "Dec"]=29

     3.3.删除元素
     delete(monthDays,"May")

     3.4.检查元素是否存在
     var value int //<<<接收value
     var isExist bool//<<<返回true/false标识是否存在
     value,isExist =monthDays["Jan"]

     另外一种方式
     value,isExist:=monthDays["Jan"]
