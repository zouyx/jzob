---
layout: post
title: Java-Metaspace会发生GC吗
permalink: /posts/2019/10/01/Java-Metaspace会发生GC吗.html
---

事件源于某一天下午跟同事闲聊的时候，跟同事谈起了Metaspace的是否会GC，双方各执一词。

认为不会的人：类的元数据，静态常量在运行时，已经整体加载到Meataspace，为什么还会需要GC呢。

认为会的人：书上是这么写，我看过，但是具体是为什么呢。

# Let‘s Go!
-----

## 永久代与Metaspace

永久代：
>>>绝大部分 Java 程序员应该都见过 "java.lang.OutOfMemoryError: PermGen space "这个异常。这里的 “PermGen space”其实指的就是方法区。不过方法区和“PermGen space”又有着本质的区别。前者是 JVM 的规范，而后者则是 JVM 规范的一种实现，并且只有 HotSpot 才有 “PermGen space”，而对于其他类型的虚拟机，如 JRockit（Oracle）、J9（IBM） 并没有“PermGen space”。由于方法区主要存储类的相关信息，所以对于动态生成类的情况比较容易出现永久代的内存溢出。最典型的场景就是，在 jsp 页面比较多的情况，容易出现永久代内存溢出。我们现在通过动态生成类来模拟 “PermGen space”的内存溢出

Metaspace
>>>移除永久代的工作从JDK1.7就开始了。JDK1.7中，存储在永久代的部分数据就已经转移到了Java Heap或者是 Native Heap。但永久代仍存在于JDK1.7中，并没完全移除，譬如符号引用(Symbols)转移到了native heap；字面量(interned strings)转移到了java heap；类的静态变量(class statics)转移到了java heap。

## 触发场景

* 加载其他类而空间不足
* 已开启Metaspcae并发GC

## 为什么Metaspcae也需要GC？

因为Java中的的ClassLoader支持开发者们在运行时加载自定义Class到Metaspace，能动态加载即需要GC监控。所以，监控类加载活动和Metaspace的使用，对于应用性能能否满足需求是有重要意义的，另外GC的统计数据也可以指明类是何时从Metaspca中卸载的。

## 如何调优

* 可以通过-XX:MetaspaceSize与-XX:MaxMetaspaceSize避免GC时扩大或者缩小Metaspace可分配的空间，如：-XX:MetaspaceSize=128m -XX:MaxMetaspaceSize=128m
* Metaspace的GC只能和CMS收集器一起使用，需要通过JVM参数打开。
* GC周期不会STW，所以程序不会感受到GC导致的停顿，但是，如果在Metaspace空间大的时候，也会有一定明显的性能损耗。

## 监控

通过VisualVM中的Classes选项卡可以online监控类加载与卸载的情况。

## 总结

我认为在这个空间能释放的空间毕竟是少，但是，也要了解其特性，调优集中精力在新生代与老年代会比较合理，
