import mill._
import mill.scalalib._

/**
 * ChiseLLM 项目 - Mill 构建配置
 * 
 * 这个配置文件帮助 IDE (如 VS Code + Metals) 正确识别 Chisel 依赖
 */
object chiselllm extends ScalaModule {
  def scalaVersion = "2.13.12"
  
  // Chisel 依赖
  override def ivyDeps = Agg(
    ivy"org.chipsalliance::chisel:6.0.0"
  )
  
  // Scala 编译选项
  override def scalacOptions = Seq(
    "-Xsource:2.13",
    "-language:reflectiveCalls",
    "-deprecation",
    "-feature",
    "-Xcheckinit",
    "-encoding", "utf-8"
  )
  
  // Chisel 编译器插件
  override def scalacPluginIvyDeps = Agg(
    ivy"org.chipsalliance:::chisel-plugin:6.0.0"
  )
}
