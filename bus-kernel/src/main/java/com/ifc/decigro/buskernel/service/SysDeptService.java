package com.ifc.decigro.buskernel.service;

import com.ifc.decigro.buskernel.entity.SysDept;
import java.util.List;

public interface SysDeptService {
    List<SysDept> list();
    void saveOrUpdate(SysDept dept);
    void deleteById(Long id);
    List<SysDept> tree();
}
