
class PIDController:
    """
    通用 PID 控制器 (Proportional-Integral-Derivative Controller)
    """
    def __init__(self, kp, ki, kd, max_step, max_i=100):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.max_step = max_step
        self.max_i = max_i
        
        self.reset()

    def reset(self):
        """ 重置内部状态 (积分项, 上次误差) """
        self.integral = 0
        self.prev_error = 0
        self.first_run = True

    def set_tunings(self, kp, ki, kd):
        """ 动态调整 PID 参数 """
        self.kp = kp
        self.ki = ki
        self.kd = kd

    def update(self, error):
        """
        计算 PID 输出
        :param error: 当前误差 (SetPoint - PV)
        :return: 控制量输出 (Output)
        """
        # 1. Proportional (比例项)
        p_term = error * self.kp

        # 2. Integral (积分项)
        self.integral += error
        # Anti-windup (积分限幅)
        self.integral = max(-self.max_i, min(self.max_i, self.integral))
        i_term = self.integral * self.ki

        # 3. Derivative (微分项)
        d_term = 0
        if not self.first_run:
            d_term = (error - self.prev_error) * self.kd
        else:
            self.first_run = False
        
        self.prev_error = error

        # 总输出
        output = p_term + i_term + d_term
        
        # 结果取整 (步进电机/舵机通常需要整数步数)
        output = int(output)

        # 4. Speed Clamping (速度/步数限制)
        # 限制单次输出的最大幅度
        if abs(output) < 1: # 最小动作阈值, 防止极小抖动
             return 0
             
        output = max(-self.max_step, min(self.max_step, output))
        
        return output
