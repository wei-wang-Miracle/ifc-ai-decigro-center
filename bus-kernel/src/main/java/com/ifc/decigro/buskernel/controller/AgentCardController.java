package com.ifc.decigro.buskernel.controller;

import com.ifc.decigro.buskernel.common.api.Result;
import com.ifc.decigro.buskernel.entity.AgentCard;
import com.ifc.decigro.buskernel.service.AgentCardService;
import com.mybatisflex.core.paginate.Page;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * MAS 智能体卡片管理控制器 (V2)
 */
@RestController
@RequestMapping("/api/agent-cards")
@Tag(name = "智能体管理", description = "MAS 智能体注册中心 API")
public class AgentCardController {

    @Autowired
    private AgentCardService agentCardService;

    @GetMapping
    @Operation(summary = "分页查询智能体列表")
    public Result<Page<AgentCard>> page(
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) String tag,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "12") int size) {
        return Result.success(agentCardService.page(keyword, tag, page, size));
    }

    @GetMapping("/{agentName}")
    @Operation(summary = "获取智能体详情")
    public Result<AgentCard> getByName(@PathVariable String agentName) {
        return Result.success(agentCardService.getByName(agentName));
    }

    @PostMapping
    @Operation(summary = "新增/更新智能体")
    public Result<Void> save(@RequestBody AgentCard agentCard) {
        agentCardService.saveOrUpdate(agentCard);
        return Result.success();
    }

    @DeleteMapping("/{agentName}")
    @Operation(summary = "删除智能体")
    public Result<Void> delete(@PathVariable String agentName) {
        agentCardService.deleteByName(agentName);
        return Result.success();
    }

    @PutMapping("/{agentName}/online")
    @Operation(summary = "智能体上线")
    public Result<Void> online(@PathVariable String agentName) {
        agentCardService.updateOnlineStatus(agentName, true);
        return Result.success();
    }

    @PutMapping("/{agentName}/offline")
    @Operation(summary = "智能体下线")
    public Result<Void> offline(@PathVariable String agentName) {
        agentCardService.updateOnlineStatus(agentName, false);
        return Result.success();
    }

    @GetMapping("/check-name")
    @Operation(summary = "检查智能体名称可用性")
    public Result<Boolean> checkName(@RequestParam String agentName) {
        boolean exists = agentCardService.existsByAgentName(agentName);
        return Result.success(!exists);
    }

    @GetMapping("/available-tools")
    @Operation(summary = "获取可绑定工具列表")
    public Result<List<String>> getAvailableTools() {
        return Result.success(agentCardService.getAvailableTools());
    }
}
