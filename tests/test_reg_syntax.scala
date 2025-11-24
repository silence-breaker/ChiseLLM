import chisel3._

// 测试 Reg(type) 旧语法在 Chisel 6.0 中是否可用
class TestRegSyntax extends Module {
  val io = IO(new Bundle {
    val in = Input(UInt(8.W))
    val out1 = Output(UInt(8.W))
    val out2 = Output(UInt(8.W))
  })
  
  // 旧语法: Reg(type)
  val counter1 = Reg(UInt(8.W))
  counter1 := io.in
  
  // 新语法: RegInit
  val counter2 = RegInit(0.U(8.W))
  counter2 := io.in
  
  io.out1 := counter1
  io.out2 := counter2
}
