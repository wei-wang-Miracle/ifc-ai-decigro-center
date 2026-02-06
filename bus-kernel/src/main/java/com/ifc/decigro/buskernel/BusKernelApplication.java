package com.ifc.decigro.buskernel;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
@MapperScan("com.ifc.decigro.buskernel.mapper")
public class BusKernelApplication {

    public static void main(String[] args) {
        SpringApplication.run(BusKernelApplication.class, args);
    }

}
