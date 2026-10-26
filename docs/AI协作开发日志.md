# AI协作开发日志

> 记录开发过程真实 bug，用于期末答辩三问。

> 说明：以下案例 1-4 来自本项目实际开发与联调过程中的问题；案例 5 为发药模块设计评审/自测阶段发现的事务风险。  
> 本项目库存扣减发生在**发药环节**，不是收费环节；收费只负责生成收费单并把处方 `paid` 置为 `True`。因此没有直接使用模板中“收费成功、库存没有扣减”的示例，而是按真实业务流程记录。  
> 第一轮提示词和迭代提示词请结合自己的真实聊天记录核对后使用，人工修改行号请以当前代码为准，不要直接照抄。

---

## Bug案例1：审计日志操作人丢失

### 1. Bug现象

登录接口的审计日志有操作人，但挂号、排班等受保护写接口产生的审计记录中，`operator_user_id` 为空。  
结果是审计表能查到“发生了什么”，但无法确认“是谁操作的”。

### 2. 第一轮提示词

对应真实开发提示词（节选）：

```text
实现医生排班、挂号后端接口。
要求挂号扣减号源使用数据库事务，并且登录、挂号、开方、收费、发药等写操作都必须进入审计日志。
```

### 3. AI第一次输出的缺陷

第一次实现时，审计中间件已经会读取：

```python
operator_id = getattr(request.state, "user_id", None)
```

但认证依赖 `get_current_user` 只返回了当前用户对象，没有把用户 ID 写入 `request.state.user_id`。  
登录接口手动设置过该值，所以登录审计正常；其他受保护写接口经过 JWT 鉴权后没有设置，导致审计操作人为空。

缺陷本质：

- 认证层和审计层之间缺少约定字段；
- 只验证了登录审计，没有验证挂号、排班等业务写接口；
- 审计日志功能“看起来能用”，但关键字段不完整。

### 4. 迭代优化提示词

```text
请检查全局审计链路的操作人来源。
要求：
1. 登录成功后写入 request.state.user_id；
2. 所有经过 get_current_user 的受保护接口，在认证成功后也写入 request.state.user_id；
3. 审计中间件继续从 request.state.user_id 读取操作人；
4. 增加测试，验证登录、挂号、排班 POST/PUT/DELETE 的审计记录都包含操作人 ID。
```

### 5. 人工修改

手动修改 `backend/app/middleware/auth.py` 的 `get_current_user` 函数，在用户校验通过后加入：

```python
request.state.user_id = user.id
```

原因：

- 审计中间件在业务路由执行完之后才读取 `request.state.user_id`；
- 认证依赖是写请求的实际入口，应该在这里统一写入操作人；
- 登录接口继续保留自己的 `request.state.user_id = user.id`。

### 6. 验证方式

```powershell
cd E:\outpatient-course-design\backend
python -m pytest tests/test_audit_middleware.py -v
python -m pytest tests/test_schedule_registration.py -v
```

手工验证：

```sql
SELECT operator_user_id, method, request_path, status_code, payload
FROM audit_logs
ORDER BY id DESC
LIMIT 10;
```

预期：挂号、排班、处方等写操作的 `operator_user_id` 不为空。

### 7. 答辩要点

- **为什么会出现**：认证层只返回用户对象，没有把操作人写入共享请求上下文；审计层依赖了一个没有在所有路径上赋值的字段。
- **怎么定位**：对比登录审计和挂号审计，发现前者有操作人、后者没有；再追踪 `request.state.user_id` 的赋值位置。
- **怎么防止复发**：把操作人写入动作集中到 `get_current_user`，并用测试覆盖登录、挂号、排班等不同类型写请求。

---

## Bug案例2：审计表字段改名后旧数据库不兼容

### 1. Bug现象

审计表模型字段从旧名称规范化为：

```text
operator_id  -> operator_user_id
path         -> request_path
created_at   -> operate_time
```

修改模型后，新建数据库可以正常工作，但项目里已有的 `his.db` 仍然保留旧列名。  
启动后访问审计查询或执行写请求时，可能出现类似：

```text
sqlite3.OperationalError: no such column: audit_logs.operator_user_id
```

### 2. 第一轮提示词

对应真实开发提示词（节选）：

```text
实现全局审计日志 middleware。
AuditLog 需要记录 operator_user_id、operate_time、request_path、method、payload。
业务代码不要手动写日志，由中间件自动写入。
```

### 3. AI第一次输出的缺陷

第一次只修改了 SQLAlchemy 模型中的数据库列名，没有考虑已有 SQLite 文件的迁移。  
对于全新测试数据库，模型建表正常；对于已有开发数据库，旧表不会被 `create_all` 自动改名，导致 ORM 查询和写入使用新列名而数据库仍是旧列名。

缺陷本质：

- 只考虑了“新建数据库”，没有考虑“已有数据不能删库重建”；
- 违反了项目约束中的“字段变更必须提供迁移脚本”；
- 开发库和测试库状态不一致，测试通过但实际运行失败。

### 4. 迭代优化提示词

```text
请为审计表字段改名补充 SQLite 迁移方案。
要求：
1. 不允许删库重建；
2. 使用 ALTER TABLE RENAME COLUMN 保留历史审计数据；
3. 脚本可重复执行，已迁移的列自动跳过；
4. 迁移后验证 audit_logs 的实际列名；
5. 不修改业务代码，只新增迁移脚本。
```

### 5. 人工修改

新增 `scripts/migrate_audit_log_columns.py`，执行：

```text
operator_id  -> operator_user_id
path         -> request_path
created_at   -> operate_time
```

脚本先读取 `PRAGMA table_info(audit_logs)`，只有旧列存在且新列不存在时才执行重命名。

执行命令：

```powershell
python scripts\migrate_audit_log_columns.py
```

验证列名：

```python
from sqlalchemy import inspect
from app.database import engine
print([c["name"] for c in inspect(engine).get_columns("audit_logs")])
```

原因：

- 课程项目已有开发数据，不能删库；
- 审计日志属于追溯数据，更不能因为字段改名丢失；
- 迁移脚本可重复执行，便于其他环境升级。

### 6. 验证方式

```powershell
cd E:\outpatient-course-design
python scripts\migrate_audit_log_columns.py
cd backend
python -m pytest tests/test_audit_middleware.py -v
```

预期：迁移脚本输出 `[RENAME]` 或 `[SKIP]`，审计查询和登录审计测试继续通过。

### 7. 答辩要点

- **为什么会出现**：只修改 ORM 模型，没有同步处理已有 SQLite 表结构。
- **怎么定位**：测试库是新库所以通过；实际开发库查询报 `no such column`；用 `PRAGMA table_info` 对比模型列名即可定位。
- **怎么防止复发**：字段变更必须同时检查模型、迁移脚本、开发库和测试库；迁移脚本要可重复执行、保留历史数据。

---

## Bug案例3：药师无法查询已收费处方

### 1. Bug现象

药房工作台需要查询已收费处方并执行发药，但药师登录后请求：

```http
GET /api/prescriptions?paid=true
```

返回 `403`，导致药师页面看不到待发药处方。

与此同时，收费员页面可以正常查询同一接口，说明接口本身可用，问题在角色权限边界。

### 2. 第一轮提示词

对应真实开发提示词（节选）：

```text
编写 Vue3 药房前端页面（pharmacist 药师角色）。
功能：
1. 药品档案管理列表，支持 CSV 导入；
2. 发药工作台：查询已经收费的处方，执行发药；
3. 未收费处方不可选择发药。
```

### 3. AI第一次输出的缺陷

后端 `GET /api/prescriptions` 最初只允许 cashier：

```python
_: User = Depends(require_role(["cashier"]))
```

药师需要读取已收费处方才能发药，但该接口没有放行 pharmacist。  
同时处方响应缺少 `dispensed` / `dispense_id` 字段，前端无法区分“待发药”和“已发药”。

缺陷本质：

- 后端权限按“收费场景”设计，没有覆盖“药房发药场景”；
- 接口复用时没有重新审视角色矩阵；
- 前端页面功能和后端权限没有一起联调。

### 4. 迭代优化提示词

```text
药师需要查询已收费处方用于发药。
请调整处方列表接口：
1. GET /api/prescriptions 允许 cashier 和 pharmacist；
2. 处方响应增加 dispensed 和 dispense_id 字段；
3. 已发药处方在药房页面显示为已发药，禁止重复发药；
4. 不要放宽处方创建接口，创建处方仍仅允许 doctor；
5. 增加药师查询、发药、重复发药的 API 测试。
```

### 5. 人工修改

修改位置：

- `backend/app/routers/prescription.py` 的 `list_prescriptions`，权限从 `cashier` 调整为 `cashier + pharmacist`；
- `backend/app/schemas/prescription.py` 增加 `dispensed`、`dispense_id`；
- `backend/app/models/prescription.py` 增加与 `DispenseRecord` 的一对一关系；
- 前端 `frontend/src/views/PharmacyView.vue` 使用 `paid=true` 查询已收费处方，并显示发药状态。

原因：

- 药师和收费员都需要读取处方，但目的不同：收费员看未收费，药师看已收费；
- 读权限放宽不等于写权限放宽，处方创建仍只允许 doctor；
- 返回发药状态可以避免前端重复调用发药接口。

### 6. 验证方式

```powershell
cd E:\outpatient-course-design\backend
python -m pytest tests/test_drug_dispense.py -v -k "pharmacist or dispense"
python -m pytest tests/test_prescription.py -v
```

手工验证：

1. cashier 完成收费；
2. pharmacist 登录；
3. 药房工作台能看到已收费处方；
4. 发药成功后状态变为“已发药”；
5. 再次发药返回 `409`。

### 7. 答辩要点

- **为什么会出现**：接口权限按单一角色设计，复用到药师场景时没有更新角色矩阵。
- **怎么定位**：用 cashier 和 pharmacist 分别调用同一接口，对比 200/403；再检查路由依赖的角色列表。
- **怎么防止复发**：权限矩阵和前端页面一起验收；读接口和写接口分别设计权限；补充跨角色 API 测试。

---

## Bug案例4：后端收紧挂号权限后，前端入口未同步

### 1. Bug现象

后端将创建挂号的 `POST /api/registrations` 收紧为仅 `admin`、`cashier` 后，doctor 和 pharmacist 的导航栏仍然显示“门诊挂号”。  
点击后页面可以打开，但提交挂号会返回 `403`，用户体验和权限表现不一致。

### 2. 第一轮提示词

对应真实开发提示词（节选）：

```text
把“挂号提交”这个动作的入口从“所有登录用户”收紧为“仅 admin 和 cashier 可操作”。
后端 POST 挂号接口 require_role 改成 ["admin", "cashier"]。
doctor、pharmacist 调用应返回 403。
前端挂号页面/挂号入口菜单，在 doctor 和 pharmacist 登录后隐藏或置灰。
```

### 3. AI第一次输出的缺陷

第一次只修改了后端：

```python
_: User = Depends(require_role(["admin", "cashier"]))
```

前端 `App.vue` 仍然无条件添加导航：

```javascript
items.push({ key: "registration", label: "门诊挂号" });
```

导致：

- 后端权限已经正确返回 403；
- 前端仍然展示入口，角色权限表达不一致；
- 用户只有在提交时才发现无权限。

缺陷本质：

- 只改了 API 权限，没有同步 UI 权限；
- 前端“隐藏入口”和后端“强制拒绝”没有作为同一条验收链路；
- 没有按 doctor、pharmacist、cashier、admin 四种角色逐一验证。

### 4. 迭代优化提示词

```text
请同步收紧前端挂号入口。
要求：
1. 增加 canRegister = admin 或 cashier；
2. navItems 仅对 admin/cashier 添加“门诊挂号”；
3. RegistrationView 渲染处增加 activeView === 'registration' && canRegister 的防御；
4. doctor/pharmacist 登录后不显示挂号入口；
5. 后端 POST /api/registrations 仍只允许 admin/cashier；
6. 不要收紧 GET /api/schedules/available 和 GET /api/registrations。
```

### 5. 人工修改

修改 `frontend/src/App.vue`：

```javascript
const canRegister = computed(() => isAdmin.value || isCashier.value);

if (canRegister.value) {
  items.push({ key: "registration", label: "门诊挂号" });
}
```

页面渲染处：

```vue
<RegistrationView
  v-if="activeView === 'registration' && canRegister"
/>
```

原因：

- 后端权限是最终防线，前端隐藏入口是体验层防线；
- 用 `canRegister` 同时控制导航和页面渲染，避免通过旧状态误入页面；
- 不修改医生待诊、可用排班查询等原有权限逻辑。

### 6. 验证方式

```powershell
cd E:\outpatient-course-design\backend
python -m pytest tests/test_schedule_registration.py -v -k "registration_permissions"
```

手工验证：

1. doctor 登录：导航无“门诊挂号”，直接 POST 挂号返回 403；
2. pharmacist 登录：导航无“门诊挂号”；
3. cashier 登录：正常挂号，号源减 1；
4. admin 登录：正常挂号，号源减 1；
5. doctor/pharmacist 仍可 GET 查询可用排班。

### 7. 答辩要点

- **为什么会出现**：后端权限和前端入口分别维护，修改时只改了一端。
- **怎么定位**：用不同角色登录对比导航，再直接调用接口对比 403/201。
- **怎么防止复发**：把“后端 403 + 前端隐藏”写进同一验收用例；权限变更时同步检查导航、页面和接口。

---

## Bug案例5：发药多药品库存扣减的事务风险

> 本案例属于设计评审/自测阶段发现的风险，不是线上事故。答辩时如实说明“在实现和测试阶段主动加固”。

### 1. Bug现象

一张处方包含多个药品时，如果按明细逐条扣减库存：

- 第一个药品库存充足，扣减成功；
- 第二个药品库存不足，抛出异常；
- 如果库存扣减没有放在同一个事务中，第一个药品的库存可能已经被扣掉，导致“部分扣减”。

### 2. 第一轮提示词

对应真实开发提示词（节选）：

```text
实现药品管理、CSV导入、发药后端接口。
发药接口约束：
1. 处方必须 paid=True 已收费；
2. 遍历处方明细扣减对应 drug.stock；
3. 任意药品库存不足抛出异常，整个事务全部回滚，返回 400。
```

### 3. AI第一次输出的缺陷

第一次实现容易出现两类问题：

1. 使用 ORM 逐条 `drug.stock -= qty`，没有 `WHERE stock >= qty` 的原子条件；
2. 库存扣减和发药记录没有放在同一个事务提交，异常时只回滚当前操作。

风险：

- 并发发药时可能读到旧库存，导致库存负数；
- 多药品处方部分成功、部分失败；
- 发药记录已写入但库存未扣，或库存扣了但发药记录未写入。

### 4. 迭代优化提示词

```text
请加固发药库存扣减。
要求：
1. 发药前校验处方 paid=True；
2. 校验处方未重复发药；
3. 先校验所有明细数量和库存；
4. 使用 UPDATE drugs SET stock = stock - :qty WHERE id = :id AND stock >= :qty 原子扣减；
5. 任意一条扣减失败，rollback 整个事务；
6. 库存扣减和 DispenseRecord 创建必须在同一个 commit 中；
7. 增加库存为 0、库存不足、多药品部分不足的测试。
```

### 5. 人工修改

修改 `backend/app/services/dispense_service.py`：

- 提取 `deduct_stock(db, drug_id, qty)`，校验数量大于 0；
- 使用原子更新条件 `Drug.stock >= quantity`；
- 在 `dispense_prescription` 中统一使用事务，任一步失败执行 `db.rollback()`；
- 通过 `DispenseRecord.prescription_id` 唯一约束防止重复发药。

原因：

- 数据库检查约束 `stock >= 0` 只能兜底，不能表达“库存足够才扣减”的业务条件；
- 原子更新可以把并发风险交给数据库；
- 发药记录和库存扣减必须同成败。

### 6. 验证方式

```powershell
cd E:\outpatient-course-design\backend
python -m pytest tests/test_core_business_units.py -v
python -m pytest tests/test_core_api_flows.py -v -k "dispense"
python -m pytest tests/test_drug_dispense.py -v
```

重点验证：

- 正常发药库存减少；
- 库存为 0 发药失败；
- 库存不足整单回滚；
- 多药品其中一个不足时，其他药品库存不变；
- 重复发药返回 409，库存不重复扣减。

### 7. 答辩要点

- **为什么会出现**：库存扣减是“读-判断-写”组合操作，如果只做内存判断或分步提交，就无法保证并发和异常下的一致性。
- **怎么定位**：构造多药品处方，让后一个药品库存不足，观察前一个药品库存是否被扣；再检查事务边界。
- **怎么防止复发**：库存扣减使用条件更新、发药记录和库存更新同一事务、数据库约束兜底、补充回滚测试。

---

## Bug案例6：待本人补充真实案例

> 这一节保留模板，建议补一个你在实际开发中真实遇到的 bug。推荐从以下方向选：
> 前端页面状态未刷新、CSV 导入错误行处理、统计日期口径、重复点击导致重复请求、接口返回字段与前端不一致等。

### 1. Bug现象

```text
【填写你实际遇到的现象，尽量写清楚：什么角色、什么操作、看到什么错误、期望什么结果】
```

### 2. 第一轮提示词

```text
【粘贴你当时真实使用的提示词，不要改写过度】
```

### 3. AI第一次输出的缺陷

```text
【写清楚 AI 第一次生成代码的具体问题：事务、权限、字段、状态、异常分支等】
```

### 4. 迭代优化提示词

```text
【写你第二次如何补充约束、复现步骤、验收标准】
```

### 5. 人工修改

```text
【文件名 + 函数名/大致行号 + 修改原因】
```

### 6. 验证方式

```text
【pytest 命令 / 页面操作步骤 / SQL 验证】
```

### 7. 答辩要点

- **为什么会出现**：
- **怎么定位**：
- **怎么防止复发**：

---

## 答辩三问速查

### 1. 这个 bug 为什么会产生？

可从以下角度回答：

- 权限只改后端没改前端；
- 只考虑了新数据库，没有考虑已有数据迁移；
- 认证层和审计层缺少字段约定；
- 事务边界不完整；
- “读-判断-写”没有使用原子条件；
- 测试只覆盖正常流程，没有覆盖异常和越权。

### 2. 你是怎么定位的？

推荐回答路径：

1. 先复现：明确角色、接口、输入和实际响应；
2. 看日志：检查后端异常、审计日志、接口状态码；
3. 查数据：用 SQL 或 SQLAlchemy 检查库存、号源、处方 paid 状态；
4. 缩小范围：对比正常与异常角色、正常与异常数据；
5. 修复后回归：运行对应 pytest，再做页面联调。

### 3. 如何防止类似问题再次出现？

- 权限变更同时检查后端接口、前端导航、页面渲染；
- 字段变更同时检查模型、迁移脚本、开发库和测试库；
- 关键写操作必须有事务和数据库约束；
- 关键业务补充单元测试和 API 测试；
- 异常分支必须写测试：库存为 0、号源耗尽、重复收费、重复发药、越权访问；
- 提交前执行：

```powershell
cd E:\outpatient-course-design\backend
python -m pytest tests/ -v
```

---

## 证据清单

答辩时可配合展示：

- `backend/tests/test_audit_middleware.py`
- `backend/tests/test_core_business_units.py`
- `backend/tests/test_core_api_flows.py`
- `backend/tests/test_schedule_registration.py`
- `backend/tests/test_charge.py`
- `backend/tests/test_drug_dispense.py`
- `scripts/migrate_audit_log_columns.py`
- `frontend/src/App.vue`
- `backend/app/middleware/auth.py`
- `backend/app/services/dispense_service.py`
- `backend/app/routers/prescription.py`

运行测试：

```powershell
cd E:\outpatient-course-design\backend
python -m pytest tests/ -v
```

预期结果：

```text
96 passed
```
