import mill._
import mill.scalalib._

/**
 * ChiseLLM 项目 - Mill 构建配置
 * 
 * 注意: 此文件仅供 reflect_env.py 内部使用，不用于 IDE 集成。
 * 请使用 `python src/run_reflect.py` 进行编译和验证。
 * 
 * 技术栈版本 (与数据集保持一致):
 *   - Scala: 2.13.12
 *   - Chisel: 6.0.0
 */
object chiselllm extends ScalaModule {
  def scalaVersion = "2.13.12"
  
  // Chisel 依赖 (Mill 1.x 语法)
  def mvnDeps = Seq(
    mvn"org.chipsalliance::chisel:6.0.0"
  )
  
  // Scala 编译选项
  def scalacOptions = Seq(
    "-Xsource:2.13",
    "-language:reflectiveCalls",
    "-deprecation",
    "-feature",
    "-Xcheckinit"
  )
  
  // Chisel 编译器插件
  def scalacPluginMvnDeps = Seq(
    mvn"org.chipsalliance:::chisel-plugin:6.0.0"
  )
  
  // 源目录
  def sources = Task.Sources(os.pwd / "tests")
}
