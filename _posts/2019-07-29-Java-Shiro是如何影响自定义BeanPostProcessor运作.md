---
layout: post
title: Java-Shiro是如何影响自定义BeanPostProcessor运作
permalink: /posts/2019/07/29/Java-Shiro是如何影响自定义BeanPostProcessor运作.html
---

介绍Shiro是如何影响自定义BeanPostProcessor运作。

# Let‘s Go!
-----

## 1.解决方案

* 隔离shiro使用的组件与业务监控的组件。
如：
shiro使用的redis实例和业务使用的redis实例不是同一个。

## 2.场景


## 3.问题现象

* 加入通过自定义BeanPostProcessor的监控组件之后,不能监控mysql和redis。

### 错误信息

```
2019-07-31 17:20:54.311 restartedMain | [] | INFO  o.s.c.s.PostProcessorRegistrationDelegate$BeanPostProcessorChecker Bean 'spring.redis-org.springframework.boot.autoconfigure.data.redis.RedisProperties' of type [org.springframework.boot.autoconfigure.data.redis.RedisProperties] is not eligible for getting processed by all BeanPostProcessors (for example: not eligible for auto-proxying)
2019-07-31 17:20:54.556 restartedMain | [] | INFO  o.s.c.s.PostProcessorRegistrationDelegate$BeanPostProcessorChecker Bean 'lettuceConnectionFactory' of type [org.springframework.data.redis.connection.lettuce.LettuceConnectionFactory] is not eligible for getting processed by all BeanPostProcessors (for example: not eligible for auto-proxying)
2019-07-31 17:20:54.693 restartedMain | [] | INFO  o.s.c.s.PostProcessorRegistrationDelegate$BeanPostProcessorChecker Bean 'shiroRedisTemplate' of type [org.springframework.data.redis.core.RedisTemplate] is not eligible for getting processed by all BeanPostProcessors (for example: not eligible for auto-proxying)
2019-07-31 17:20:54.883 restartedMain | [] | INFO  o.s.c.s.PostProcessorRegistrationDelegate$BeanPostProcessorChecker Bean 'shiroConfig' of type [com.common.security.config.ShiroConfig$$EnhancerBySpringCGLIB$$37c03ac9] is not eligible for getting processed by all BeanPostProcessors (for example: not eligible for auto-proxying)
2019-07-31 17:20:57.525 restartedMain | [] | INFO  o.s.c.s.PostProcessorRegistrationDelegate$BeanPostProcessorChecker Bean 'redisCacheManager' of type [com.common.security.cache.RedisCacheManager] is not eligible for getting processed by all BeanPostProcessors (for example: not eligible for auto-proxying)
2019-07-31 17:20:58.060 restartedMain | [] | INFO  o.s.c.s.PostProcessorRegistrationDelegate$BeanPostProcessorChecker Bean 'sessionFactory' of type [com.common.security.config.SessionFactory] is not eligible for getting processed by all BeanPostProcessors (for example: not eligible for auto-proxying)
2019-07-31 17:20:58.227 restartedMain | [] | INFO  o.s.c.s.PostProcessorRegistrationDelegate$BeanPostProcessorChecker Bean 'sessionManager' of type [org.apache.shiro.web.session.mgt.DefaultWebSessionManager] is not eligible for getting processed by all BeanPostProcessors (for example: not eligible for auto-proxying)
2019-07-31 17:20:58.725 restartedMain | [] | INFO  o.s.c.s.PostProcessorRegistrationDelegate$BeanPostProcessorChecker Bean 'securityManager' of type [org.apache.shiro.web.mgt.DefaultWebSecurityManager] is not eligible for getting processed by all BeanPostProcessors (for example: not eligible for auto-proxying)
2019-07-31 17:32:15.457 restartedMain | [] | INFO  o.s.c.s.PostProcessorRegistrationDelegate$BeanPostProcessorChecker Bean 'mybatis-plus-com.baomidou.mybatisplus.spring.boot.starter.MybatisPlusProperties' of type [com.baomidou.mybatisplus.spring.boot.starter.MybatisPlusProperties] is not eligible for getting processed by all BeanPostProcessors (for example: not eligible for auto-proxying)
2019-07-31 17:32:16.404 restartedMain | [] | INFO  o.s.c.s.PostProcessorRegistrationDelegate$BeanPostProcessorChecker Bean 'mybatisPlusConfig' of type [com.common.config.MybatisPlusConfig$$EnhancerBySpringCGLIB$$48de742d] is not eligible for getting processed by all BeanPostProcessors (for example: not eligible for auto-proxying)
2019-07-31 17:32:16.704 restartedMain | [] | INFO  o.s.c.s.PostProcessorRegistrationDelegate$BeanPostProcessorChecker Bean 'performanceInterceptor' of type [com.baomidou.mybatisplus.plugins.PerformanceInterceptor] is not eligible for getting processed by all BeanPostProcessors (for example: not eligible for auto-proxying)
2019-07-31 17:32:16.793 restartedMain | [] | INFO  o.s.c.s.PostProcessorRegistrationDelegate$BeanPostProcessorChecker Bean 'paginationInterceptor' of type [com.baomidou.mybatisplus.plugins.PaginationInterceptor] is not eligible for getting processed by all BeanPostProcessors (for example: not eligible for auto-proxying)
2019-07-31 17:32:17.156 restartedMain | [] | INFO  o.s.c.s.PostProcessorRegistrationDelegate$BeanPostProcessorChecker Bean 'com.baomidou.mybatisplus.spring.boot.starter.MybatisPlusAutoConfiguration' of type [com.baomidou.mybatisplus.spring.boot.starter.MybatisPlusAutoConfiguration$$EnhancerBySpringCGLIB$$61864f65] is not eligible for getting processed by all BeanPostProcessors (for example: not eligible for auto-proxying)
2019-07-31 17:32:17.334 restartedMain | [] | INFO  o.s.c.s.PostProcessorRegistrationDelegate$BeanPostProcessorChecker Bean 'org.springframework.boot.autoconfigure.jdbc.DataSourceConfiguration$Generic' of type [org.springframework.boot.autoconfigure.jdbc.DataSourceConfiguration$Generic] is not eligible for getting processed by all BeanPostProcessors (for example: not eligible for auto-proxying)
2019-07-31 17:32:19.705 restartedMain | [] | INFO  o.s.c.s.PostProcessorRegistrationDelegate$BeanPostProcessorChecker Bean 'spring.datasource-org.springframework.boot.autoconfigure.jdbc.DataSourceProperties' of type [org.springframework.boot.autoconfigure.jdbc.DataSourceProperties] is not eligible for getting processed by all BeanPostProcessors (for example: not eligible for auto-proxying)
```

## 4.问题分析

### 初步分析

* 通过查看错误信息log发现,其中会包含redis与mysql，是否这些提示就是和无法使用BeanPostProcessor有关系呢？
* 通过not eligible for auto-proxying信息查找到对应的代码，为什么是：not eligible for auto-proxying 不适用于自动代理？
```java
public Object postProcessAfterInitialization(Object bean, String beanName) {
            if (bean != null && !(bean instanceof BeanPostProcessor) && !this.isInfrastructureBean(beanName) && this.beanFactory.getBeanPostProcessorCount() < this.beanPostProcessorTargetCount && logger.isInfoEnabled()) {
                logger.info("Bean '" + beanName + "' of type [" + bean.getClass().getName() + "] is not eligible for getting processed by all BeanPostProcessors (for example: not eligible for auto-proxying)");
            }

            return bean;
        }
```
* 仔细观察之下发现，log会归为几类：shiro、redis、jdbc、session。redis和jdbc都是需要监控的组件，会影响bbp吗？先假定不会。那么就剩下shiro了。
* 尝试把shiro屏蔽，错误信息中的log没了一大部分，自定义的bbp也能进去了，为什么呢？

### 深入分析
* shiroFilter依赖了securityManager，securityManager依赖了userRealm，userRealm为了获取AuthenticationInfo和AuthorizationInfo又依赖了redis和mysql。
* ShiroFitlerFactoryBean这个bean继承了FactoryBean，将SecurityManager提前初始化，并无将初始化过程托管给spring，导致其所有引用的类都没有托管给spring，所以自定义bpp无效。
#### 测试代码

结果：helloA
证明：增加了factorybean之后，并不会走自定义bpp

去掉factorybean之后，托管给spring初始化之后
结果：
sayHello InitBBean before
sayHello InitABean before
helloA
sayHello InitABean after
sayHello InitBBean after

##### 测试用例
```java 
@RunWith(SpringJUnit4ClassRunner.class)
@ContextConfiguration(classes = Conf.class)
public class BeanPostProcessorTestTest {

    @Autowired
    BeanPostProcessorATest test;

    @Test
    public void sayHello() {
        test.sayHello();
    }
}
```
##### 被测试代码
```java
public interface BeanPostProcessorTest {

    void sayHello();
}
```
```java
public class BeanPostProcessorATest implements BeanPostProcessorTest {

    @Override
    public void sayHello(){
        System.out.println("helloA");
    }
}
```
```java
public class BeanPostProcessorBTest implements BeanPostProcessorTest {

    @Override
    public void sayHello(){
        System.out.println("helloB");
    }
}
```
```java
@Configuration
@ComponentScan
public class Conf {
}
```
```java

@Component
public class InitABean implements FactoryBean<BeanPostProcessorATest>,BeanPostProcessor
{

    private BeanPostProcessorATest instance;
    @Override
    public Object postProcessBeforeInitialization(Object bean, String beanName) throws BeansException {
        if(bean instanceof BeanPostProcessorATest){
            ProxyFactoryBean pfb = new ProxyFactoryBean();
            pfb.setTarget(bean);
            pfb.setAutodetectInterfaces(false);
            NameMatchMethodPointcutAdvisor advisor = new NameMatchMethodPointcutAdvisor();
            advisor.addMethodName("sayHello");
            advisor.setAdvice((MethodInterceptor) invocation -> {
                System.out.println("sayHello InitABean before");
                Object result = invocation.getMethod().invoke(invocation.getThis(), invocation.getArguments());
                System.out.println("sayHello InitABean after");
                return result;
            });
            pfb.addAdvisor(advisor);

            return pfb.getObject();
        }
        return bean;
    }

    @Override
    public Object postProcessAfterInitialization(Object bean, String beanName) throws BeansException {
        return bean;
    }

    @Override
    public BeanPostProcessorATest getObject() throws Exception {
        if (this.instance == null) {
            this.instance = new BeanPostProcessorATest();
        }
        return this.instance;
    }

    @Override
    public Class<?> getObjectType() {
        return BeanPostProcessorATest.class;
    }

    @Override
    public boolean isSingleton() {
        return true;
    }
}
```
```java

@Component
public class InitBBean implements BeanPostProcessor
{
    @Override
    public Object postProcessBeforeInitialization(Object bean, String beanName) throws BeansException {
        if(bean instanceof BeanPostProcessorATest){
            ProxyFactoryBean pfb = new ProxyFactoryBean();
            pfb.setTarget(bean);
            pfb.setAutodetectInterfaces(false);
            NameMatchMethodPointcutAdvisor advisor = new NameMatchMethodPointcutAdvisor();
            advisor.addMethodName("sayHello");
            advisor.setAdvice((MethodInterceptor) invocation -> {
                System.out.println("sayHello InitBBean before");
                Object result = invocation.getMethod().invoke(invocation.getThis(), invocation.getArguments());
                System.out.println("sayHello InitBBean after");
                return result;
            });
            pfb.addAdvisor(advisor);

            return pfb.getObject();
        }
        return bean;
    }

    @Override
    public Object postProcessAfterInitialization(Object bean, String beanName) throws BeansException {
        return bean;
    }
}
```
