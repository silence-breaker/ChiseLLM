import chisel3._
import chisel3.util._

// 10进制计数器模块
// 每个时钟周期递增,从0计数到9后回到0
class TenTimer extends Module {
  val io = IO(new Bundle {
    val enable = Input(Bool())       // 使能信号
    val reset_count = Input(Bool())  // 计数器复位信号
    val count = Output(UInt(4.W))    // 当前计数值 (0-9)
    val overflow = Output(Bool())    // 溢出信号(计数到9时为高)
  })
  
  // 计数寄存器
  val counter = RegInit(0.U(4.W))
  
  // 计数逻辑
  when(io.reset_count) {
    // 复位计数器
    counter := 0.U
  }.elsewhen(io.enable) {
    // 使能时进行计数
    when(counter === 9.U) {
      counter := 0.U  // 计数到9后回到0
    }.otherwise {
      counter := counter + 1.U
    }
  }
  
  // 输出逻辑
  io.count := counter
  io.overflow := (counter === 9.U) && io.enable
}
